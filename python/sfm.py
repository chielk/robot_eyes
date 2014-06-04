import numpy as np
import utils
from mpl_toolkits.mplot3d.axes3d import Axes3D
import matplotlib.pyplot as plt



def structure_from_motion(pointviewmat, args):
    '''
    Create a 3D model based on a set of matching 2D points!
    '''
    # Remove columns of points that do not persist throughout the pointviewmat
    m, n, _ = pointviewmat.shape
    persisting_points = [pt_idx for pt_idx in xrange(n) if
                         np.array([0, 0]) not in pointviewmat[:, pt_idx, :]]
    if args.verbosity:
        print "Of {} points".format(n),
    pointviewmat = pointviewmat[:, persisting_points, :]
    m, n, _ = pointviewmat.shape
    if args.verbosity:
        print "{} points persist throughout the sequence".format(n)

    # Subtract the mean for each image at the same time
    pointviewmat -= np.mean(pointviewmat, axis=1, keepdims=True)

    # Our pointviewmat is m x n x 2, we'll make it 2m x n
    pointviewmat = \
        np.vstack(tuple([pointviewmat[m_, :, :].T for m_ in xrange(m)]))

    U, W, V = np.linalg.svd(pointviewmat)
    # Enforce rank 3
    U = U[:, :3]
    W = np.diag(W[:3])
    V = V[:, :3]

    # Create motion and structure matrices from svd
    M = np.dot(U, W)
    S = V
    # M, S = remove_affine_amb(m, M, S)
    if args.output_file:
        utils.writepcd(args.output_file, S)
        if not args.no_visualization:
            fig = plt.figure(figsize=plt.figaspect(.5))
            ax1 = fig.add_subplot(121, projection='3d')
            ax1.scatter(S[:, 0], S[:, 1], S[:, 2])

            #ax2 = fig.add_subplot(212, projection='3d')
            #ax2.plot_trisurf(S[:, 0], S[:, 1], S[:, 2])
            plt.show()


def remove_affine_amb(m, M, S):
    ''' Find least squares solution for A L A^T = I d '''
    super_A = np.zeros((3 * m, 9))
    rhs = np.zeros((3 * m, 1))
    for m_idx in xrange(m):
        a1 = M[m_idx * 2, :]
        a2 = M[m_idx * 2 + 1, :]

        # Add the constraints
        super_A[m_idx * 3, :] = \
            np.tile(a1, 3) * np.repeat(a1, 3)
        rhs[m_idx * 3, 0] = 1
        super_A[m_idx * 3, :] = \
            np.tile(a2, 3) * np.repeat(a2, 3)
        rhs[m_idx * 3 + 1, 0] = 1
        super_A[m_idx * 3, :] = \
            np.tile(a1, 3) * np.repeat(a2, 3)
        # rhs is 0 by default

    U, W, V = np.linalg.svd(super_A)
    # Enforce rank 3
    #U = U[:3, :9]
    #W = np.diag(W[:])
    #V = V[:3, :]

    print 'u', U.shape, 'w', W.shape,'v', V.shape
    # x = V . W^-1 . U^T b
    d = np.array(np.dot(U.T, rhs), dtype=float)
    print d, W

    r = sum(W > 1)
    L = np.dot(V, np.hstack((d.T[0][:r] / W[:r], np.zeros(9 - r))))
    L = np.reshape(L, (3, 3))
    print 'L\n', L

    L = utils.nearPD(L, nit=30)
    print 'L nearest positive definite\n', L

    # Perform cholesky decomposition, update structure and motion matrices
    C = np.linalg.cholesky(L)
    M = np.array(np.dot(M, C), dtype=float)
    S = np.array(np.dot(C.T, S.T).T, dtype=float)
    return M, S
