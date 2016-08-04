"""
Filename: DynLinEcon.py
Authors: Sebastian Graves
Provides a class called DLE to convert and solve dynamic linear economics (as set out in Hansen & Sargent (2013)) as LQ problems.
"""

import numpy as np
from quantecon import LQ
from quantecon import solve_discrete_lyapunov
from sympy import Matrix
from pylab import array

class DLE(object):
    """
    This class is for analysing economies that are characterised by matrices defining information and shocks {a22, c2, ub, ud}, production technology {phic, phig, phii, gamma, 
    deltak, thetak}, household technology {deltah, thetah, lambda, pih} and the scalar {beta}.

    Section 5.5 of HS2013 describes how to map these matrices into those of a LQ problem. 
    
    This class solves the associated LQ problem for such economies, and provides methods to find the non-stochastic steady state and simulate quantities and prices for the economy.
    """

    def __init__(self, information, technology, preferences):

        self.a22, self.c2, self.ub, self.ud = information
        self.phic, self.phig, self.phii, self.gamma, self.deltak, self.thetak = technology
        self.beta, self.llambda, self.pih, self.deltah, self.thetah = preferences
        
        """ Computation of the dimension of the structural parameter matrices """
        
        self.nb,self.nh = self.llambda.shape
        self.nd,self.nc = self.phic.shape
        self.nz,self.nw = self.c2.shape
        junk,self.ng = self.phig.shape
        self.nk,self.ni = self.thetak.shape

        """ Creation of various useful matrices """

        uc = np.hstack((np.eye(self.nc),np.zeros((self.nc,self.ng))))
        ug = np.hstack((np.zeros((self.ng,self.nc)),np.eye(self.ng)))

        phiin = np.linalg.inv(np.hstack((self.phic,self.phig)))
        phiinc = uc.dot(phiin)
        phiing = ug.dot(phiin)
        b11 = - self.thetah.dot(phiinc).dot(self.phii)
        a1 = self.thetah.dot(phiinc).dot(self.gamma)
        a12 = np.vstack((self.thetah.dot(phiinc).dot(self.ud), np.zeros((self.nk,self.nz))))

        """ Creation of the A Matrix for the state transition of the LQ problem"""

        a11 = np.vstack((np.hstack((self.deltah,a1)), np.hstack((np.zeros((self.nk,self.nh)),self.deltak))))
        self.A = np.vstack((np.hstack((a11,a12)), np.hstack((np.zeros((self.nz,self.nk+self.nh)),self.a22))))

        """ Creation of the B Matrix for the state transition of the LQ problem"""

        b1 = np.vstack((b11,self.thetak))
        self.B = np.vstack((b1,np.zeros((self.nz,self.ni))))

        """ Creation of the C Matrix for the state transition of the LQ problem"""

        self.C = np.vstack((np.zeros((self.nk+self.nh,self.nw)),self.c2))

        """ Define R,W and Q for the payoff function of the LQ problem """

        self.H = np.hstack((self.llambda,self.pih.dot(uc).dot(phiin).dot(self.gamma),self.pih.dot(uc).dot(phiin).dot(self.ud)-self.ub,-self.pih.dot(uc).dot(phiin).dot(self.phii)))

        self.G = ug.dot(phiin).dot(np.hstack((np.zeros((self.nd,self.nh)),self.gamma,self.ud,-self.phii)))

        self.S = (self.G.T.dot(self.G) + self.H.T.dot(self.H))/2

        self.nx = self.nh+self.nk+self.nz
        self.n = self.ni+self.nh+self.nk+self.nz

        self.R = self.S[0:self.nx,0:self.nx]
        self.W = self.S[self.nx:self.n,0:self.nx]
        self.Q = self.S[self.nx:self.n,self.nx:self.n]

        """ Use quantecon's LQ code to solve our LQ problem """

        lq = LQ(self.Q, self.R, self.A, self.B, self.C, N=self.W, beta=self.beta)

        self.P, self.F, self.d = lq.stationary_values()

        """ Construct output matrices for our economy using the solution to the LQ problem"""

        self.A0 = self.A - self.B.dot(self.F)

        self.Sh = self.A0[0:self.nh,0:self.nx]
        self.Sk = self.A0[self.nh:self.nh+self.nk,0:self.nx]
        self.Sk1 = np.hstack((np.zeros((self.nk,self.nh)),np.eye(self.nk),np.zeros((self.nk,self.nz))))
        self.Si = -self.F
        self.Sd = np.hstack((np.zeros((self.nd,self.nh+self.nk)),self.ud))
        self.Sb = np.hstack((np.zeros((self.nb,self.nh+self.nk)),self.ub))
        self.Sc = uc.dot(phiin).dot(-self.phii.dot(self.Si) + self.gamma.dot(self.Sk1) + self.Sd)
        self.Sg = ug.dot(phiin).dot(-self.phii.dot(self.Si) + self.gamma.dot(self.Sk1) + self.Sd)
        self.Ss = self.llambda.dot(np.hstack((np.eye(self.nh),np.zeros((self.nh,self.nk+self.nz))))) + self.pih.dot(self.Sc)

        """ Calculate eigenvalues of A0 """
        self.A110 = self.A0[0:self.nh+self.nk,0:self.nh+self.nk]
        self.endo = np.linalg.eigvals(self.A110)
        self.exo = np.linalg.eigvals(self.a22)

        """ Construct matrices for Lagrange Multipliers """

        self.Mk = -2*np.asscalar(self.beta)*(np.hstack((np.zeros((self.nk,self.nh)),np.eye(self.nk),np.zeros((self.nk,self.nz))))).dot(self.P).dot(self.A0)
        self.Mh = -2*np.asscalar(self.beta)*(np.hstack((np.eye(self.nh),np.zeros((self.nh,self.nk)),np.zeros((self.nh,self.nz))))).dot(self.P).dot(self.A0)
        self.Ms = -(self.Sb - self.Ss)
        self.Md = -(np.linalg.inv(np.vstack((self.phic.T,self.phig.T))).dot(np.vstack((self.thetah.T.dot(self.Mh) + self.pih.T.dot(self.Ms),-self.Sg))))
        self.Mc = -(self.thetah.T.dot(self.Mh) + self.pih.T.dot(self.Ms))
        self.Mi = -(self.thetak.T.dot(self.Mk))

        #I made up the matrices for Mk and Mh but they seem to work. I also had to put a minus in front of everything to get same as the Matlab code
        
        """Find non-stochastic steady state of economy"""
    def compute_steadystate(self, nnc=2): #nnc is the position of the constant in the state vector
        zx = Matrix(np.eye(self.A0.shape[0])-self.A0)
        self.zz = zx.nullspace()
        self.zz = array(self.zz)
        self.zz = self.zz.T
        self.zz = zz = self.zz/self.zz[nnc] 
        self.css = self.Sc.dot(self.zz).astype(float)
        self.sss = self.Ss.dot(self.zz).astype(float)
        self.iss = self.Si.dot(self.zz).astype(float)
        self.dss = self.Sd.dot(self.zz).astype(float)
        self.bss = self.Sb.dot(self.zz).astype(float)
        self.kss = self.Sk.dot(self.zz).astype(float)
        self.hss = self.Sh.dot(self.zz).astype(float)

        """ Simulate quantities and prices for our economy """
    def compute_sequence(self, x0, ts_length=None, Pay=None):
        lq = LQ(self.Q, self.R, self.A, self.B, self.C, N=self.W, beta=self.beta)
        xp, up, wp = lq.compute_sequence(x0, ts_length)
        self.h = self.Sh.dot(xp)
        self.k = self.Sk.dot(xp)
        self.i = self.Si.dot(xp)
        self.b = self.Sb.dot(xp)
        self.d = self.Sd.dot(xp)
        self.c = self.Sc.dot(xp)
        self.g = self.Sg.dot(xp)
        self.s = self.Ss.dot(xp)

        """Value of J-period risk-free bonds"""
        # See p.145: Equation (7.11.2)
        e1 = np.zeros((1,self.nc))
        e1[0,0] = 1
        self.R1_Price = np.empty((ts_length+1,1))
        self.R2_Price = np.empty((ts_length+1,1))
        self.R5_Price = np.empty((ts_length+1,1))
        for i in range(ts_length+1):
            self.R1_Price[i,0] = self.beta*e1.dot(self.Mc).dot(np.linalg.matrix_power(self.A0,1)).dot(xp[:,i])/e1.dot(self.Mc).dot(xp[:,i])
            self.R2_Price[i,0] = self.beta**2*e1.dot(self.Mc).dot(np.linalg.matrix_power(self.A0,2)).dot(xp[:,i])/e1.dot(self.Mc).dot(xp[:,i])
            self.R5_Price[i,0] = self.beta**5*e1.dot(self.Mc).dot(np.linalg.matrix_power(self.A0,5)).dot(xp[:,i])/e1.dot(self.Mc).dot(xp[:,i])

        """Gross rates of return on 1-period risk-free bonds"""
        self.R1_Gross = 1/self.R1_Price

        """Net rates of return on J-period risk-free bonds"""
        # See p.148: log of gross rate of return, divided by j
        self.R1_Net = np.log(1/self.R1_Price)/1
        self.R2_Net = np.log(1/self.R2_Price)/2
        self.R5_Net = np.log(1/self.R5_Price)/5

        """Value of asset whose payout vector is Pay*xt"""
        # See p.145: Equation (7.11.1)
        if isinstance(Pay,np.ndarray) == True:
            self.Za = Pay.T.dot(self.Mc)
            self.Q = solve_discrete_lyapunov(self.A0.T*self.beta**0.5,self.Za)
            self.q = self.beta/(1-self.beta)*np.trace(self.C.T.dot(self.Q).dot(self.C))
            self.Pay_Price = np.empty((ts_length+1,1))
            self.Pay_Gross = np.empty((ts_length+1,1))
            self.Pay_Gross[0,0] = np.nan
            for i in range(ts_length+1):
                self.Pay_Price[i,0] = (xp[:,i].T.dot(self.Q).dot(xp[:,i]) + self.q)/e1.dot(self.Mc).dot(xp[:,i])
            for i in range(ts_length):
                self.Pay_Gross[i+1,0] = self.Pay_Price[i+1,0]/(self.Pay_Price[i,0] - Pay.dot(xp[:,i]))
        return

        """ Create Impulse Response Functions """
    def irf(self, ts_length=100, shock=None):
        
        if type(shock) != np.ndarray:
            shock = np.vstack((np.ones((1,1)),np.zeros((self.nw-1,1)))) #Default is to select first element of w

        self.c_irf = np.empty((ts_length,self.nc))
        self.s_irf = np.empty((ts_length,self.nb))
        self.i_irf = np.empty((ts_length,self.ni))
        self.k_irf = np.empty((ts_length,self.nk))
        self.h_irf = np.empty((ts_length,self.nh))
        self.g_irf = np.empty((ts_length,self.ng))
        self.d_irf = np.empty((ts_length,self.nd))
        self.b_irf = np.empty((ts_length,self.nb))

        for i in range(ts_length):
            self.c_irf[i,:] = self.Sc.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.s_irf[i,:] = self.Ss.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.i_irf[i,:] = self.Si.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.k_irf[i,:] = self.Sk.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.h_irf[i,:] = self.Sh.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.g_irf[i,:] = self.Sg.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.d_irf[i,:] = self.Sd.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T
            self.b_irf[i,:] = self.Sb.dot(np.linalg.matrix_power(self.A0,i)).dot(self.C).dot(shock).T

        return

        """ Compute canonical preferences """
        """ Uses auxiliary problem of 9.4.2, with the preference shock process reintroduced
            Calculates pihat, llambdahat and ubhat for the equivalent canonical household technology """
    def canonical(self):
        Ac1 = np.hstack((self.deltah,np.zeros((self.nh,self.nz))))
        Ac2 = np.hstack((np.zeros((self.nz,self.nh)),self.a22))
        Ac = np.vstack((Ac1,Ac2))
        Bc = np.vstack((self.thetah,np.zeros((self.nz,self.nc))))
        Cc = np.vstack((np.zeros((self.nh,self.nw)),self.c2))
        Rc1 = np.hstack((self.llambda.T.dot(self.llambda),-self.llambda.T.dot(self.ub)))    
        Rc2 = np.hstack((-self.ub.T.dot(self.llambda),self.ub.T.dot(self.ub)))
        Rc = np.vstack((Rc1,Rc2))
        Qc = self.pih.T.dot(self.pih)
        Nc = np.hstack((self.pih.T.dot(self.llambda),-self.pih.T.dot(self.ub)))
        
        lq_aux = LQ(Qc, Rc, Ac, Bc, N = Nc, beta=self.beta)

        P1, F1, d1 = lq_aux.stationary_values()
        
        self.F_b = F1[:,0:self.nh]
        self.F_f = F1[:,self.nh:]
        
        self.pihat = np.linalg.cholesky(self.pih.T.dot(self.pih) + self.beta.dot(self.thetah.T).dot(P1[0:self.nh,0:self.nh]).dot(self.thetah)).T
        self.llambdahat = self.pihat.dot(self.F_b)
        self.ubhat = - self.pihat.dot(self.F_f)
        
        return 
