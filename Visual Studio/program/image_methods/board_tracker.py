"""Track the same physical chessboard while the camera moves.

The initial four corners define square identity. Optical flow keeps that
identity between frames; periodic chessboard detection corrects drift when
the pattern is visible. A lost or contradictory view is never used for moves.
"""
import cv2
import numpy as np

from image_methods.detect_points import detect_board_corners


class BoardTrackingError(RuntimeError):
    """The current image cannot safely be mapped to the known board."""


class BoardTracker:
    def __init__(self, size=(800, 800), detection_interval=24, periodic_detection=True):
        self.size = size
        self.detection_interval = detection_interval
        self.periodic_detection = periodic_detection
        self.corners = None
        self.previous_gray = None
        self.frames_since_detection = 0

    def _validate_corners(self, corners, shape):
        corners = np.asarray(corners, dtype=np.float32).reshape(4, 2)
        height, width = shape[:2]
        if not np.isfinite(corners).all():
            raise BoardTrackingError("Board corners are invalid.")
        if np.any(corners[:, 0] < 0) or np.any(corners[:, 0] >= width):
            raise BoardTrackingError("Board left the camera view.")
        if np.any(corners[:, 1] < 0) or np.any(corners[:, 1] >= height):
            raise BoardTrackingError("Board left the camera view.")
        if not cv2.isContourConvex(corners.reshape(4, 1, 2)):
            raise BoardTrackingError("Board corners no longer form a convex quadrilateral.")
        if cv2.contourArea(corners) < 0.015 * width * height:
            raise BoardTrackingError("Board is too small to track reliably.")
        sides = np.linalg.norm(corners - np.roll(corners, -1, axis=0), axis=1)
        if min(sides) < 0.10 * min(width, height):
            raise BoardTrackingError("Board edge is too short to track reliably.")
        return corners

    def initialize(self, image, corners):
        """Lock onto current physical corners, supplied by detection or user."""
        gray = self._gray(image)
        self.corners = self._validate_corners(corners, image.shape)
        self.previous_gray = gray
        self.frames_since_detection = 0
        return self.warp_current(image)

    @staticmethod
    def _gray(image):
        if image is None or image.ndim not in (2, 3):
            raise BoardTrackingError("Camera frame is missing or invalid.")
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    def _track_corners(self, gray):
        mask = np.zeros_like(self.previous_gray)
        cv2.fillConvexPoly(mask, self.corners.astype(np.int32), 255)
        points = cv2.goodFeaturesToTrack(
            self.previous_gray, maxCorners=350, qualityLevel=0.01,
            minDistance=6, mask=mask,
        )
        if points is None or len(points) < 20:
            return None
        moved, status, _ = cv2.calcOpticalFlowPyrLK(
            self.previous_gray, gray, points, None,
            winSize=(25, 25), maxLevel=3,
        )
        if moved is None:
            return None
        returned, back_status, _ = cv2.calcOpticalFlowPyrLK(
            gray, self.previous_gray, moved, None,
            winSize=(25, 25), maxLevel=3,
        )
        if returned is None:
            return None
        good = (
            (status.ravel() == 1) & (back_status.ravel() == 1)
            & (np.linalg.norm(points.reshape(-1, 2) - returned.reshape(-1, 2), axis=1) < 1.5)
        )
        if np.count_nonzero(good) < 16:
            return None
        source = points.reshape(-1, 2)[good]
        destination = moved.reshape(-1, 2)[good]
        matrix, inliers = cv2.findHomography(source, destination, cv2.RANSAC, 3.0)
        if matrix is None or inliers is None:
            return None
        if np.count_nonzero(inliers) < 14 or np.mean(inliers) < 0.60:
            return None
        projected = cv2.perspectiveTransform(source.reshape(-1, 1, 2), matrix).reshape(-1, 2)
        errors = np.linalg.norm(projected - destination, axis=1)
        if np.median(errors[inliers.ravel() == 1]) > 2.5:
            return None
        return cv2.perspectiveTransform(self.corners.reshape(-1, 1, 2), matrix).reshape(4, 2)

    def update(self, image):
        """Accept one nearby frame or raise without changing the last good lock."""
        if self.corners is None:
            raise BoardTrackingError("Board has not been calibrated.")
        gray = self._gray(image)
        if gray.shape != self.previous_gray.shape:
            raise BoardTrackingError("Camera resolution changed; relock the board.")
        tracked = self._track_corners(gray)
        detected = None
        attempted_detection = tracked is None or (
            self.periodic_detection and self.frames_since_detection >= self.detection_interval
        )
        if attempted_detection:
            detected = detect_board_corners(image, fast=tracked is not None)
        if tracked is None and detected is None:
            raise BoardTrackingError("Board lost or hidden; no reliable features remain.")

        side = float(np.mean(np.linalg.norm(
            self.corners - np.roll(self.corners, -1, axis=0), axis=1,
        )))
        max_step = max(12.0, 0.18 * side)
        if tracked is not None:
            tracked = self._validate_corners(tracked, image.shape)
            if np.max(np.linalg.norm(tracked - self.corners, axis=1)) > max_step:
                raise BoardTrackingError("Board jumped suddenly; relock before playing.")
        if detected is not None:
            detected = self._validate_corners(detected, image.shape)
            # The checker pattern alone does not identify a8. Preserve the
            # orientation from the prior tracked frame.
            reference = tracked if tracked is not None else self.corners
            options = [np.roll(detected, shift, axis=0) for shift in range(4)]
            detected = min(options, key=lambda candidate: np.mean(
                np.linalg.norm(candidate - reference, axis=1),
            ))
            distance = np.max(np.linalg.norm(detected - reference, axis=1))
            if distance > max(8.0, 0.04 * side):
                if tracked is not None:
                    raise BoardTrackingError("Board detector and motion tracker disagree.")
                if distance > max_step:
                    raise BoardTrackingError("Board jumped suddenly; relock before playing.")

        candidate = detected if detected is not None else tracked
        old_view = self.warp_current(self.previous_gray)
        new_view = self._warp(image, candidate)
        old_gray = self._gray(old_view)
        new_gray = self._gray(new_view)
        difference = cv2.absdiff(old_gray, new_gray)
        width, height = self.size
        heavily_changed = 0
        for row in range(8):
            for column in range(8):
                x, y = column * width // 8, row * height // 8
                cell = difference[
                    y + height // 40:y + height // 8 - height // 40,
                    x + width // 40:x + width // 8 - width // 40,
                ]
                if np.mean(cell > 35) > 0.25:
                    heavily_changed += 1
        if heavily_changed > 10:
            raise BoardTrackingError("Most of the board appearance changed; relock it.")

        self.corners = candidate
        self.previous_gray = gray
        self.frames_since_detection = 0 if attempted_detection else self.frames_since_detection + 1
        return new_view

    def warp_current(self, image):
        if self.corners is None:
            raise BoardTrackingError("Board has not been calibrated.")
        return self._warp(image, self.corners)

    def _warp(self, image, corners):
        width, height = self.size
        target = np.float32([
            [0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1],
        ])
        transform = cv2.getPerspectiveTransform(corners, target)
        return cv2.warpPerspective(image, transform, self.size)
