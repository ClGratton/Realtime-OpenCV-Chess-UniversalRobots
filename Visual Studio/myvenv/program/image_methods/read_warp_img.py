import cv2
import numpy as np

def get_warp_img(img, dir_path, img_resize):
    # Load corresponding points
    pts1 = np.load(dir_path+'/chess_board_warp_prespective.npz')['pts1']
    pts2 = np.load(dir_path+'/chess_board_warp_prespective.npz')['pts2']
    
    try:
        # Find homography matrix H
        H, mask = cv2.findHomography(pts1, pts2)
        
        # Check if H is None (homography estimation failed)
        if H is None:
            raise Exception("Homography estimation failed.H is null")
        
        # Warp the image using the homography matrix
        result = cv2.warpPerspective(img, H, img_resize)
        
        return result
    
    except Exception as e:
        print(f"Error: {e}")
        return None
