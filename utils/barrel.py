import numpy as np

# import cv2 as cv
# import glob

ret = 0.0777360425494162

mtx = np.array(
    [
        [1.38218941e03, 0.00000000e00, 2.83321583e02],
        [0.00000000e00, 1.38583007e03, 2.31981042e02],
        [0.00000000e00, 0.00000000e00, 1.00000000e00],
    ]
)

dist = np.array([[0.11889878, 0.49877114, 0.00225353, -0.00669254, -1.36621538]])

rvecs = (
    np.array([[0.07881963], [0.16522169], [-2.19108968]]),
    np.array([[0.14235467], [0.0240879], [-0.00049002]]),
    np.array([[0.09699567], [0.14240043], [-1.68052885]]),
    np.array([[0.10721937], [0.1386671], [-1.60966301]]),
    np.array([[0.10132057], [0.13876036], [-1.58664335]]),
    np.array([[0.09545136], [0.13973289], [-1.58342166]]),
)

tvecs = (
    np.array([[4.86751019], [3.12167117], [54.49182722]]),
    np.array([[-2.27427069], [-0.72676168], [54.06003323]]),
    np.array([[-3.28633879], [3.70883802], [54.80815935]]),
    np.array([[5.62925574], [-0.59636922], [53.93044505]]),
    np.array([[6.10541424], [1.92934572], [54.35906401]]),
    np.array([[-1.60934195], [1.23681629], [54.37902461]]),
)


# termination criteria
# criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
# objp = np.zeros((7*7,3), np.float32)
# objp[:,:2] = np.mgrid[0:7,0:7].T.reshape(-1,2)

# Arrays to store object points and image points from all the images.
# objpoints = [] # 3d point in real world space
# imgpoints = [] # 2d points in image plane.

# images = glob.glob('utils/*.jpg')

# for fname in images:
#    img = cv.imread(fname)
#    gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

# Find the chess board corners
#    ret, corners = cv.findChessboardCorners(gray, (7,7), None)

# If found, add object points, image points (after refining them)
#    if ret == True:
#        objpoints.append(objp)

#        corners2 = cv.cornerSubPix(gray,corners, (11,11), (-1,-1), criteria)
#        imgpoints.append(corners2)

#        # Draw and display the corners
#        cv.drawChessboardCorners(img, (7,7), corners2, ret)
#        cv.imshow('img', img)
#        cv.waitKey(500)

# cv.destroyAllWindows()

# ret, mtx, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
# print(f"ret: {ret}")
# print(f"mtx: {mtx}")
# print(f"dist: {dist}")
# print(f"rvecs: {rvecs}")
# print(f"tvecs: {tvecs}")


# img = cv.imread('utils/captured_image_1.jpg')
# h,  w = img.shape[:2]
# newcameramtx, roi = cv.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))

# undistort
# dst = cv.undistort(img, mtx, dist, None, newcameramtx)

# crop the image
# x, y, w, h = roi
# dst = dst[y:y+h, x:x+w]
# cv.imwrite('calibresult.png', dst)
