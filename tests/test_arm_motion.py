"""Check that a UR Cartesian home pose uses the Cartesian motion API."""
import unittest
import importlib
import sys
import types
from unittest.mock import Mock, patch

from config import home_position, travel_offset


class ArmMotionTests(unittest.TestCase):
    def test_pick_place_and_cartesian_home(self):
        # The unit test does not require the robot's optional URX driver.
        fake_module = types.ModuleType("arm_methods.robotiq_two_finger_gripper")
        fake_module.Robotiq_Two_Finger_Gripper = Mock()
        with patch.dict(sys.modules, {fake_module.__name__: fake_module}):
            move_piece_module = importlib.import_module("arm_methods.movePiece")
        robot = Mock()
        source = [0.30, -0.20, 0.10, 0.0, 3.14, 0.0]
        target = [0.35, -0.20, 0.10, 0.0, 3.14, 0.0]
        source_original, target_original = source.copy(), target.copy()

        move_piece_module.movePiece(robot, source, target)

        self.assertEqual(source, source_original)
        self.assertEqual(target, target_original)
        robot.movej.assert_not_called()
        poses = [call.args[0] for call in robot.movel.call_args_list]
        self.assertEqual(poses[0][2], source[2] + travel_offset)
        self.assertEqual(poses[-1], home_position)
        self.assertEqual(robot.movel.call_count, 7)
        self.assertTrue(all(call.kwargs["wait"] for call in robot.movel.call_args_list))
        gripper = fake_module.Robotiq_Two_Finger_Gripper.return_value
        self.assertEqual(gripper.close_gripper.call_count, 1)
        self.assertEqual(gripper.open_gripper.call_count, 2)


if __name__ == "__main__":
    unittest.main()
