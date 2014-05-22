import numpy as np
from itertools import izip
import math
import cv2


def epipole(fundamental):
    """
    Calculate the epipoles e, e' given a fundemental matrix.

    We know that
    F e = 0
    F^T e' = 0

    so we can use svd to find the answer(s), as this gives us
    the nullspace of the matrix in the last matrix.
    """
    _, _, v = np.linalg.svd(fundamental)
    _, _, v_prime = np.linalg.svd(fundamental.T)
    return v[:, -1], v_prime[:, -1]


def estimate_camera_matrices(img_files, normalized, ransac_iterations,
                             verbosity):
    """

    """
    # TODO call eightpoint correctly.


def eightpoint(img_files, normalized, ransac_iterations=None,
               threshold=1e-3, data_set="", verbose=False):
    """
    Perform the eightpoint algorithm for a given set of images.
    Normalized is a boolean indicating whether we should use the
    normalized eightpoint algorithm or not. If ransac_iterations
    is >0 , we use ransac to find the best fundamental matrix.
    """
    # initialize sift detector
    sift = cv2.SIFT()
    # initialize params for FLANN
    index_params = {'algorithm': 0,    # FLANN_INDEX_KDTREE,
                    'trees': 5}
    search_params = {'checks': 50}

    # For bear, crop image to 200:1400, 600:1800
    if data_set == "TeddyBear":
        crop = [200, 1400, 600, 1800]
    else:  # For house, don't crop image? TODO
        crop = False

    img1 = read_and_crop(img_files[0], crop, grayscale=True)
    # Compute keypoints
    kp1, des1 = sift.detectAndCompute(img1, None)

    for img2_name in img_files[1:]:
        # Read the next file
        img2 = read_and_crop(img2_name, crop, grayscale=True)
        kp2, des2 = sift.detectAndCompute(img2, None)

        # Use flann to find best matches
        flann = cv2.FlannBasedMatcher(index_params, search_params)
        matches = flann.knnMatch(des1, des2, k=2)
        # Get arrays of keypoints that match (and filter out bad ones)
        matches1, matches2 = filter_matches(kp1, kp2, matches, ratio=0.5)
        # TODO make ratio arg
        drawmatches(img1, img2, matches1, matches2, verbose)

        if normalized:
            unnormalized_m1 = matches1
            unnormalized_m2 = matches2
            matches1, T1 = normalize(matches1, verbose)
            matches2, T2 = normalize(matches2, verbose)

        # Compute fundamental matrix!
        # FIXME flow of program is just.. ugly
        if not ransac_iterations:
            F = fundamental(matches1, matches2)
        else:
            inliers, F = \
                fundamental_ransac(matches1, matches2,
                                   ransac_iterations, threshold,
                                   verbose)
        if normalized:
            F = np.dot(T2.T, np.dot(F, T1))
            matches1 = unnormalized_m1
            matches2 = unnormalized_m2
        if ransac_iterations:
            matches1 = matches1[inliers]
            matches2 = matches2[inliers]

        print F
        # e, e_prime = epipole(F)
        draw_epipolar_lines(img1, img2, F, matches1, matches2)

        # Update
        img1, kp1, des1 = img2, kp2, des2


def read_and_crop(img_name, crop, grayscale=True):
    """
    Read an image by its name, and crop it.
    """
    img = cv2.imread(img_name)
    # TODO enable 1D image cropping
    if crop:
        min_height, max_height, min_width, max_width = crop
        img = img[min_height:max_height, min_width:max_width, :]
    if grayscale:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def filter_matches(kp1, kp2, matches, ratio=0.75):
    """
    Filter matches based on the notion that at the second closest match
    should be at least at <ratio> distance from the best match.

    Returns two vectors, with on each row corresponding keypoints.
    """
    m1, m2 = [], []
    for m in matches:
        if len(m) >= 2 and m[0].distance < ratio * m[1].distance:
            m1.append(list(kp1[m[0].queryIdx].pt) + [1])
            m2.append(list(kp2[m[0].trainIdx].pt) + [1])
    return np.array(m1), np.array(m2)


def normalize(points, verbosity):
    """
    Normalize a given set of point.
    """
    mean = np.mean(points[:, :2], axis=0)
    d = np.mean(np.sqrt(np.sum(np.power(points[:, :2] - mean, 2),
                               axis=1)))
    sqrt2d = math.sqrt(2) / float(d)
    T = np.array([[sqrt2d, 0,      -mean[0] * sqrt2d],
                  [0,      sqrt2d, -mean[1] * sqrt2d],
                  [0,      0,      1]])
    normalized_points = np.dot(T, points.T).T

    if verbosity > 1:
        print "Normalized points set, centroid is now {}".format(
            np.mean(normalized_points, axis=0)) + \
            ", should be close to zero."
        print "Mean distance to centroid is {}, should be sqrt(2)".format(
            np.mean(np.sqrt(np.sum(np.power(normalized_points[:, :2], 2),
                                   axis=1))))
    return normalized_points, T


def draw_epipolar_lines(img1, img2, fundamental, matches1, matches2,
                        verbosity=0):
    """
    Draw two given images and draw epipolar lines on both.
    """

    def draw_epipolar_line(view, point, line, x0, x1, offset_pt,
                           offset_ln, color):
        # Lines are in form Ax + By + C = 0, which gives us
        point = (int(point[0]) + offset_pt, int(point[1]))
        a, b, c = line
        y0 = int((-a * x0 - c) / float(b))
        y1 = int((-a * x1 - c) / float(b))
        cv2.line(view,
                 (int(offset_ln + x0), y0),
                 (int(offset_ln + x1), y1),
                 color)
        cv2.circle(view, point, radius=20, color=color)

    # Create storage for both images
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    view = np.zeros((max(h1, h2), w1 + w2, 3), np.uint8)
    view[:h1, :w1, 0] = img1
    view[:h2, w1:, 0] = img2
    view[:, :, 1] = view[:, :, 0]
    view[:, :, 2] = view[:, :, 0]

    for x, x_prime in izip(matches1, matches2):
        color = tuple([np.random.randint(0, 255)
                       for _ in xrange(3)])
        l_prime = np.dot(fundamental, x)
        l = np.dot(fundamental.T, x_prime)

        # l is the line corresponding to x_prime
        draw_epipolar_line(view, x_prime, l, 0, w2, w1, 0, color)
        # l_prime is the line corresponding to x
        draw_epipolar_line(view, x, l_prime, 0, w1, 0, w1, color)

    # Resize for easy display
    view = cv2.resize(view, (0, 0), fx=0.25, fy=0.25)
    cv2.imshow("Epipolar lines", view)
    cv2.waitKey()


def drawmatches(img1, img2, kp1, kp2, verbosity=0):
    """
    Since drawMatches is not yet included in opencv 2.4.9, we
    added a simple function that visualises matches in different
    colors, based on (mostly copied from):

    http://stackoverflow.com/questions/11114349/how-to-visualize-
        descriptor-matching-using-opencv-module-in-python

    It accepts two grayscale images and keypoints, plus an array
    of matches. It will only consider the first match.
    """
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    # Create storage for eventual matches
    view = np.zeros((max(h1, h2), w1 + w2, 3), np.uint8)
    view[:h1, :w1, 0] = img1
    view[:h2, w1:, 0] = img2
    view[:, :, 1] = view[:, :, 0]
    view[:, :, 2] = view[:, :, 0]

    for p1, p2 in izip(kp1, kp2):
        # draw the keypoints
        # print m.queryIdx, m.trainIdx, m.distance
        color = tuple([np.random.randint(0, 255)
                       for _ in xrange(3)])
        cv2.line(view,
                 (int(p1[0]),
                  int(p1[1])),
                 (int(p2[0] + w1),
                  int(p2[1])),
                 color)
    # Resize for easy display
    view = cv2.resize(view, (0, 0), fx=0.25, fy=0.25)
    cv2.imshow("Matches", view)
    cv2.waitKey()


def fundamental_ransac(matches1, matches2, ransac_iterations,
                       threshold, verbose=False):
    """Use RANSAC to find the best fundamental matrix"""

    # 1. Randomly sample matches, save in N x 8 matrix
    random_indices = np.random.randint(0, len(matches1),
                                       (ransac_iterations, 8))

    # 2. Define some function that can evaluate each sample's F
    def evaluate(indices, matches1, matches2, threshold=1e-4):
        selected1 = matches1[indices]
        selected2 = matches2[indices]
        F = fundamental(selected1, selected2)

        rest1 = matches1[[i for i in xrange(len(matches1))
                          if i not in indices]]
        rest2 = matches2[[i for i in xrange(len(matches1))
                          if i not in indices]]
        inliers = []
        outliers = []
        for idx, (p1, p2) in enumerate(izip(rest1, rest2)):
            Fp1 = np.dot(F, p1)
            # Calculate sampson distance
            d = (np.dot(p2.T, Fp1) ** 2) / np.sum(np.power(Fp1, 2))
            if d < threshold:
                inliers.append(idx)
            else:
                outliers.append(idx)
        return inliers, F

    # 3. Feed it all to the parallel queue!
    from parallel_queue import process_parallel
    list_of_numinliers_and_fundamentals = \
        process_parallel(random_indices, evaluate, num_processes=4,
                         verbose=True, matches1=matches1,
                         matches2=matches2, threshold=threshold)

    # 4. Based on evaluation function, now contains <len_inliers>, F
    srtd = sorted(list_of_numinliers_and_fundamentals,
                  key=lambda tup: len(tup[0]))
    return srtd[-1]


def fundamental(matches1, matches2):
    """
    Compute the fundamental matrix given two sets of matches.
    """
    # [ x1 x1'  x1 y1'  x1   y1 x1'  y1 y1'  y1   x1'  y1'  1 ]
    A = np.tile(matches2, (1, 3)) * np.repeat(matches1, 3, 1)
    # Compute svd of A
    U, D, V = np.linalg.svd(A)
    # Take columns/rows of interest TODO find out if this is needed?
    # Uf = U[:, 0:3]
    # Df = np.diag(D[0:3])
    # Vf = V[0:3]

    # entries of F are in last column of v, which is the nullspace of A
    F = np.reshape(V[:, -1], (3, 3))
    Uf, Df, Vf = np.linalg.svd(F)

    # Set smallest singular value to zero
    Df = np.diag(Df)
    Df[2, 2] = 0  # Ensure non-singularity (Hartley & Zissermann p. 280)
    # Recompute F
    F = np.dot(Uf, np.dot(Df, Vf.T))

    return F
