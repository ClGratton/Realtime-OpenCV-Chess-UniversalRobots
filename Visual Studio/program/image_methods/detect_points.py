"""Chessboard image calibration with automatic detection and manual fallback."""
import cv2
import numpy as np

WINDOW = "Chessboard calibration"


def _ordered_corners(corners):
    """Order a quadrilateral as top-left, top-right, bottom-right, bottom-left."""
    points = np.asarray(corners, dtype=np.float32).reshape(4, 2)
    center = points.mean(axis=0)
    angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
    points = points[np.argsort(angles)]
    start = int(np.argmin(points[:, 0] + points[:, 1]))
    points = np.roll(points, -start, axis=0)
    if points[1, 0] < points[-1, 0]:
        points = points[[0, 3, 2, 1]]
    return points


def detect_board_corners(image, fast=False):
    """Detect 7x7 inner intersections and extrapolate the board's outer corners."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    detector = getattr(cv2, "findChessboardCornersSB", None)
    if detector is not None:
        flags = 0 if fast else cv2.CALIB_CB_EXHAUSTIVE | cv2.CALIB_CB_ACCURACY
        found, corners = detector(gray, (7, 7), flags=flags)
    else:
        found, corners = cv2.findChessboardCorners(
            gray,
            (7, 7),
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
        )
        if found:
            criteria = (
                cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                40,
                0.001,
            )
            corners = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)

    if not found or corners is None or len(corners) != 49:
        return None

    detected = np.asarray(corners, dtype=np.float32).reshape(7, 7, 2)
    canonical = np.array(
        [[column + 1, row + 1] for row in range(7) for column in range(7)],
        dtype=np.float32,
    )
    transform, _ = cv2.findHomography(canonical, detected.reshape(-1, 2), 0)
    if transform is None:
        return None
    board_grid = np.array(
        [[0, 0], [8, 0], [8, 8], [0, 8]], dtype=np.float32
    ).reshape(-1, 1, 2)
    outer = cv2.perspectiveTransform(board_grid, transform).reshape(4, 2)
    return _ordered_corners(outer)


def _draw_circle(event, x, y, flags, state):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        state["point"] = (x, y)


def orient_corners(corners, a8_index):
    """Return image corners ordered as physical a8, h8, h1, a1."""
    if a8_index not in range(4):
        raise ValueError("a8 corner index must be between zero and three.")
    return np.roll(np.asarray(corners).reshape(4, 2), -a8_index, axis=0)


def _ask_a8(image, corners):
    display = image.copy()
    for index, point in enumerate(corners):
        x, y = map(int, point)
        cv2.circle(display, (x, y), 10, (0, 0, 255), 3)
        cv2.putText(display, str(index + 1), (x + 12, y - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
    cv2.putText(display, "Which corner is a8? Press 1-4", (15, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
    print("Identify the physical a8 corner: press its displayed number (1-4).")
    while True:
        cv2.imshow(WINDOW, display)
        key = cv2.waitKey(30)
        if ord("1") <= key <= ord("4"):
            cv2.destroyWindow(WINDOW)
            return orient_corners(corners, key - ord("1")).astype(int).tolist()


def get_points(image, numOfPoints=4):
    if numOfPoints != 4:
        raise ValueError("Chessboard calibration expects four outer corners.")
    resized = cv2.resize(image, (800, 800))
    automatic = detect_board_corners(resized)
    if automatic is not None:
        print("Rilevati automaticamente i quattro angoli della scacchiera.")
        return _ask_a8(resized, automatic)

    print("Rilevamento automatico non riuscito: seleziona i quattro angoli a mano.")
    state = {"point": None}
    points = []
    display = resized.copy()
    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, _draw_circle, state)
    print("Doppio clic su un angolo, poi premi 'a' per aggiungerlo.")
    print("Ordine: alto-sinistra, alto-destra, basso-destra, basso-sinistra.")
    while len(points) < 4:
        cv2.imshow(WINDOW, display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("a") and state["point"] is not None:
            point = state["point"]
            points.append([int(point[0]), int(point[1])])
            cv2.circle(display, point, 5, (0, 0, 255), -1)
            state["point"] = None
    cv2.destroyWindow(WINDOW)
    return _ask_a8(resized, points)
