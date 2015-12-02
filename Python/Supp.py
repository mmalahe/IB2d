'''-------------------------------------------------------------------------

 IB2d is an Immersed Boundary Code (IB) for solving fully coupled non-linear 
 	fluid-structure interaction models. This version of the code is based off of
	Peskin's Immersed Boundary Method Paper in Acta Numerica, 2002.

 Author: Nicholas A. Battista
 Email:  nick.battista@unc.edu
 Date Created: May 27th, 2015\
 Python 3.5 port by: Christopher Strickland
 Institution: UNC-CH

 This code is capable of creating Lagrangian Structures using:
 	1. Springs
 	2. Beams (*torsional springs)
 	3. Target Points
	4. Muscle-Model (combined Force-Length-Velocity model, "HIll+(Length-Tension)")

 One is able to update those Lagrangian Structure parameters, e.g., 
 spring constants, resting lengths, etc
 
 There are a number of built in Examples, mostly used for teaching purposes. 
 
 If you would like us to add a specific muscle model, 
 please let Nick (nick.battista@unc.edu) know.
 
 For the Python port, I am going to throw a lot of supporting functions into
    here for convinence. That way they get loaded all at once, and are called
    by their name in an intuitive way. The functions (with their subfunctions
    following) are here in this order:
    -- please_Move_Lagrangian_Point_Positions
    -- give_NonZero_Delta_Indices_XY
    -- give_Eulerian_Lagrangian_Distance
    -- give_Delta_Kernel
    -- give_1D_NonZero_Delta_Indices
    -- please_Move_Massive_Boundary
    -- please_Update_Massive_Boundary_Velocity
    -- D
    -- DD

----------------------------------------------------------------------------'''

import numpy as np
from math import sqrt

################################################################################
#
# FUNCTION: Moves Lagrangian Point Positions by doing the integral,
#
#           " xLag_Next = xLag_Prev + dt* int( u(x,t) delta( x - xLag_n ) dX ) "
#
################################################################################

def please_Move_Lagrangian_Point_Positions(u, v, xL_P, yL_P, xL_H, yL_H, x, y,\
    dt, grid_Info,porous_Yes):
    ''' Moves Lagrangian point positions
    
    Returns:
        xL_Next: 
        yL_Next:'''


    # Grid Info. grid_Info is a list
    Nx =   grid_Info[0]
    Ny =   grid_Info[1]
    Lx =   grid_Info[2]
    Ly =   grid_Info[3]
    dx =   grid_Info[4]
    dy =   grid_Info[5]
    supp = int(grid_Info[6])
    Nb =   grid_Info[7]
    ds =   grid_Info[8]


    # Find indices where the delta-function kernels are non-zero for both x and y.
    xInds,yInds = give_NonZero_Delta_Indices_XY(xL_H, yL_H, Nx, Ny, dx, dy, supp)

    # ReSize the xL_H and yL_H matrices for use in the Dirac-delta function
    #        values to find distances between corresponding Eulerian data and them
    xLH_aux = xL_H % Lx; xL_H_ReSize = []
    yLH_aux = yL_H % Ly; yL_H_ReSize = []
    for ii in range(supp**2):
       xL_H_ReSize.append(xLH_aux)
       yL_H_ReSize.append(yLH_aux)
    #xL_H and yL_H are vectors. stack them along a new column axis 
    xL_H_ReSize = np.stack(xL_H_ReSize,axis=-1)
    yL_H_ReSize = np.stack(yL_H_ReSize,axis=-1)

    # Finds distance between specified Eulerian data and nearby Lagrangian data
    distX = give_Eulerian_Lagrangian_Distance(x[xInds], xL_H_ReSize, Lx)
    distY = give_Eulerian_Lagrangian_Distance(y[yInds], yL_H_ReSize, Ly)

    # Obtain the Dirac-delta function values.
    delta_X = give_Delta_Kernel(distX, dx)
    delta_Y = give_Delta_Kernel(distY, dy)

    # Perform Integral
    move_X, move_Y = give_Me_Perturbed_Distance(u,v,dx,dy,delta_X,delta_Y,xInds,yInds)

    # Update the Lagrangian Point Position.
    xL_Next = xL_P + (dt) * move_X
    yL_Next = yL_P + (dt) * move_Y


    # Shift so that all values are in [0,Lx or Ly).
    if not porous_Yes:
        xL_Next = xL_Next % Lx
        yL_Next = yL_Next % Ly

    return (xL_Next, yL_Next)



################################################################################
# FUNCTION: Computes the integral to move each Lagrangian Pt!
################################################################################

def give_Me_Perturbed_Distance(u,v,dx,dy,delta_X,delta_Y,xInds,yInds):
    ''' Computes the integral to move each Lagrangian Pt.
    
    Args:
        u:        x-component of velocity
        v:        y-component of velocity
        delta_X:  values of Dirac-delta function in x-direction
        delta_Y:  values of Dirac-delta function in y-direction
        xInds:    x-Indices on fluid grid
        yInds:    y-Indices on fluid grid'''

    row,col = xInds.shape
    mat_X = np.zeros((row,col))  # Initialize matrix for storage
    mat_Y = np.zeros((row,col))  # Initialize matrix for storage
    for ii in range(row):
        for jj in range(col):
            
            # Get Eulerian indices to use for velocity grids, u and 
            xID = xInds[ii,jj]
            yID = yInds[ii,jj]
            
            # Compute integrand 'stencil' of velocity x delta for each Lagrangian Pt!
            mat_X[ii,jj] = u[yID,xID]*delta_X[ii,jj]*delta_Y[ii,jj]
            mat_Y[ii,jj] = v[yID,xID]*delta_X[ii,jj]*delta_Y[ii,jj]

            
    # Approximate Integral of Velocity x Delta for each Lagrangian Pt!
    move_X = mat_X.sum(1) * (dx*dy)
    move_Y = mat_Y.sum(1) * (dx*dy)

    return (move_X, move_Y)




############################################################################################
#
# FUNCTION: finds the indices on the Eulerian grid where the 1D Dirac-delta
# kernel is possibly non-zero in BOTH (x,y) directions
#
############################################################################################

def give_NonZero_Delta_Indices_XY(xLag, yLag, Nx, Ny, dx, dy, supp):
    ''' Find indices where 1D Dirac-delta kernel is non-zero in both (x,y)
    
    Args:
        xLag: gives x-coordinate of Lagrangian position
        yLag: gives y-coordinate of Lagrangian position
        Nx:   # of Eulerian grid pts. in x-dimension
        Ny:   # of Eulerian grid pts. in y-dimension
        dx:   spatial-step along x-dimension of Eulerian grid
        dy:   spatial-step along y-dimension of Eulerian grid
        supp: size of support of the Dirac-delta kernel (should be even)
        
    Returns:
        xInds: x index
        yInds: y index'''


    #Give x-dimension Non-Zero Delta Indices
    xIndsAux = give_1D_NonZero_Delta_Indices(xLag, Nx, dx, supp)

    #Repeat x-Indices for Non-Zero y-Indices!
    xInds = []
    for ii in range(supp):
       xInds.append(xIndsAux) #Sets up x-INDEX matrix bc we consider BOTH dimensions
    #this is a list of matrices. concatenate in horiz direction
    xInds = np.concatenate(xInds,1)


    #Give y-dimension Non-Zero Delta Indices
    yIndsAux = give_1D_NonZero_Delta_Indices(yLag, Ny, dy, supp)

    #Repeat y-Indices for Non-Zero x-Indices!
    yInds = []
    for ii in range(supp):
        for jj in range(supp):
            yInds.append(yIndsAux[:,ii]) #Sets up y-INDEX matrix bc we consider
                                         #  BOTH dimensions
    #this is a list of 1-D arrays. stack them along a new column axis
    yInds = np.stack(yInds,axis=-1)
    
    #these are indices, so return ints
    return (xInds.astype('int'),yInds.astype('int'))



################################################################################
#
# FUNCTION distance between Eulerian grid data, x, and Lagrangian grid data, y, 
#          at specifed pts typically and makes sure the distances are 
#          correct for a periodic [0,L] domain.
#
################################################################################

def give_Eulerian_Lagrangian_Distance(x, y, L):
    ''' Find dist. between Eulerian grid data and Lagrangian grid data.
    [0,L] has periodic boundary condition, so in actuality, the greatest
    distance possible is L/2.
    
    Args:
        x,y: two matrices that you find the distance between
            (x-typically Eulerian data, y-typically Lagrangian data)
        L: length of domain, i.e., [0,L]
        
    Returns:
        distance: distance'''

    row,col = x.shape
    distance = abs( x - y )
    for ii in range(row):
        for jj in range(col):
            #Note: need to make sure that taking correct value
            distance[ii,jj] = min(distance[ii,jj],L-distance[ii,jj])
    
    return distance



###########################################################################
#
# FUNCTION: computes a discrete approx. to a 1D Dirac-delta function over a
# specified matrix, x, and spatial step-size, dx. It will have support in
# [x-2dx, x+2dx]
#
###########################################################################

def give_Delta_Kernel(x,dx):
    ''' Computes discrete approx. to 1D delta func over x in [x-2dx,x+2dx].
    
    Args:
        x:  Values in which the delta function will be evaulated
        dx: Spatial step-size of grid
        
    Returns:
        delta: delta function with support [x-2dx,x+2dx]'''

    # Computes Dirac-delta Approximation.
    RMAT = abs(x)/dx

    #Initialize delta
    delta = RMAT

    #Loops over to find delta approximation
    row,col = x.shape
    for ii in range(row):
        for jj in range(col):
            
            r = RMAT[ii,jj]
            
            if r<1:
                delta[ii,jj] = ( (3 - 2*r + sqrt(1 + 4*r - 4*r*r) ) / (8*dx) )
            elif (r<2) and (r>=1):
                delta[ii,jj] = ( (5 - 2*r - sqrt(-7 + 12*r - 4*r*r) ) / (8*dx) )

    return delta



###########################################################################
#
# FUNCTION finds the indices on the Eulerian grid where the 1D Dirac-delta
# kernel is possibly non-zero is x-dimension.
#
###########################################################################

def give_1D_NonZero_Delta_Indices(lagPts_j, N, dx, supp):
    ''' Find the indices on Eulerian grid where 1D delta is non-zero in x dim.
    
    Args:
        lagPts_j: matrix of lagrangian pts for specific coordinate, j= x or y.
        N:        # spatial resolution of Eulerian grid in each dimension
        dx:       Spatial step-size on Eulerian (fluid) grid
        supp:     Size of support of the Dirac-delta kernel (should be even)
        
    Returns:
        indices'''


    # Finds the index of the lower left Eulerian pt. to Lagrangian pt..
    ind_Aux = np.floor(lagPts_j/dx + 1)

    # Get all the different x indices that must be considered.
    indices = []
    for ii in range(supp):
        indices.append(ind_Aux)
    #this is a list of 1-D arrays. stack them along a new column axis
    indices = np.stack(indices,axis=-1)
    #
    for ii in range(supp):
        indices[:,ii] = indices[:,ii] + -supp/2+1+ii

    # Translate indices between {0,2,..,N-1}
    indices = (indices-1 % N)

    return indices
    
################################################################################
#
# FUNCTION: update 'massive' immersed boundary position
#
################################################################################

def please_Move_Massive_Boundary(dt_step,mass_info,mVelocity):
    ''' Update 'massive' immersed boundary position
    
    Args:
        dt_step: desired time-step for this position
        mass_info: col 1: lag index for mass pt
                   col 2: massive x-Lag Value
                   col 3: massive y-Lag Value
                   col 4: 'mass-spring' stiffness parameter
                   col 5: MASS parameter value
        mVelocity  col 1: x-directed Lagrangian velocity
                   col 2: y-directed Lagrangian velocity

    Returns:
        mass_info:
        massLagsOld:'''

    massLagsOld = np.array(mass_info[:,(1, 2)])

    # update x-Positions
    mass_info[:,1] = mass_info[:,1] + dt_step*mVelocity[:,0]

    # update y-Positions
    mass_info[:,2] = mass_info[:,2] + dt_step*mVelocity[:,1]
    
    return (mass_info, massLagsOld)
    
    
    
############################################################################################
#
# FUNCTION: update 'massive' immersed boundary velocity
#
############################################################################################

def please_Update_Massive_Boundary_Velocity(dt_step,mass_info,mVelocity,\
    F_Mass_Bnd,gravity_Info):
    ''' Update 'massive' immersed boundary velocity
    
    Args:
        dt_step: desired time-step for this position
        mass_info:   col 1: lag index for mass pt
                     col 2: massive x-Lag Value
                     col 3: massive y-Lag Value
                     col 4: 'mass-spring' stiffness parameter
                     col 5: MASS parameter value
        mVelocity    col 1: x-directed Lagrangian velocity
                     col 2: y-directed Lagrangian velocity
        F_Mass_Bnd   col 1: x-directed Lagrangian force
                     col 2: y-directed Lagrangian force
        gravity_Info col 1: flag if considering gravity (0 = NO, 1 = YES)
                     col 2: x-component of gravity vector (NORMALIZED PREVIOUSLY)
                     col 3: y-component of gravity vector (NORMALIZED PREVIOUSLY)
                     
    Returns:
        mVelocity_h:'''

    ids = mass_info[:,0]

    if gravity_Info[0] == 1:
         
        g = 9.80665 #m/s^2
        
        # update x-Velocity
        mVelocity_h[:,0] = mVelocity[:,0] - dt_step * \
        ( F_Mass_Bnd[ids,0]/mass_info[:,4] - g*gravity_Info[1] )

        # update y-Velocity
        mVelocity_h[:,1] = mVelocity[:,1] - dt_step * \
        ( F_Mass_Bnd[ids,1]/mass_info[:,4] - g*gravity_Info[2] )
        
    else:
        
        # update x-Velocity
        mVelocity_h[:,0] = mVelocity[:,0] - dt_step*F_Mass_Bnd[ids,0]/mass_info[:,4]

        # update y-Velocity
        mVelocity_h[:,1] = mVelocity[:,1] - dt_step*F_Mass_Bnd[ids,1]/mass_info[:,4]
        
    return mVelocity_h



########################################################################
#
# FUNCTION: Finds CENTERED finite difference approximation to 1ST
# Derivative in specified direction by input, dz, and 'string'. 
# Note: It automatically accounts for periodicity of the domain.
#
########################################################################

def D(u,dz,string):
    ''' Finds centered 1st derivative in specified direction
    
    Args:
        u:      velocity 
        dz:     spatial step in "z"-direction
        string: specifies which 1ST derivative to take (to enforce periodicity)
        
    Returns:
        u_z:'''

    length = u.shape[0]
    u_z = np.zeros((length,length))

    if string=='x':

        #For periodicity on ends
        u_z[:,0] = ( u[:,1] - u[:,length-1] ) / (2*dz)
        u_z[:,-1]= ( u[:,0] - u[:,length-2] ) / (2*dz)

        #Standard Centered Difference 
        for jj in range(1,length-1):
            u_z[:,jj] = ( u[:,jj+1] - u[:,jj-1] ) / (2*dz)

    elif string=='y':
        
        #For periodicity on ends
        u_z[0,:] = ( u[1,:] - u[length-1,:] ) / (2*dz)
        u_z[length-1,:] = ( u[0,:] - u[length-2,:] ) / (2*dz)

        #Standard Centered Difference 
        for jj in range(1,length-1):
            u_z[jj,:] = ( u[jj+1,:] - u[jj-1,:] ) / (2*dz)
        
    else:
        
        print('\n\n\n ERROR IN FUNCTION D FOR COMPUTING 1ST DERIVATIVE\n')
        print('Need to specify which desired derivative, x or y.\n\n\n')
           
    return u_z


########################################################################
#
# FUNCTION: Finds CENTERED finite difference approximation to 2ND
# DERIVATIVE in z direction, specified by input and 'string' 
# Note: It automatically accounts for periodicity of the domain.
#
########################################################################

def DD(u,dz,string):
    ''' Finds centered 2nd derivative in z direction, specified by input & string
    
    Args:
        u:      velocity 
        dz:     spatial step in "z"-direction
        string: specifies which 2ND derivative to take (to enforce periodicity)
        
    Returns:
        u_zz:'''

    length = u.shape[0]
    u_zz = np.zeros((length,length))

    if string=='x':

        #For periodicity on ends
        u_zz[:,0] =  ( u[:,1] - 2*u[:,0]   + u[:,length-1] )   / (dz**2)
        u_zz[:,-1] = ( u[:,0] - 2*u[:,length-1] + u[:,length-2] ) / (dz**2)

        #Standard Upwind Scheme (Centered Difference)
        for jj in range(1,length-1):
            u_zz[:,jj] = ( u[:,jj+1] - 2*u[:,jj] + u[:,jj-1] ) / (dz**2)

    elif string=='y':

        #For periodicity on ends
        u_zz[0,:] =  ( u[1,:] - 2*u[0,:]   + u[length-1,:] )   / (dz**2)
        u_zz[-1,:]= ( u[0,:] - 2*u[length-1,:] + u[length-2,:] ) / (dz**2)

        #Standard Upwind Scheme (Centered Difference)
        for jj in range(1,length-1):
            u_zz[jj,:] = ( u[jj+1,:] - 2*u[jj,:] + u[jj-1,:] ) / (dz**2)

    else:
        
        print('\n\n\n ERROR IN FUNCTION DD FOR COMPUTING 2ND DERIVATIVE\n')
        print('Need to specify which desired derivative, x or y.\n\n\n')
        
    return u_zz

