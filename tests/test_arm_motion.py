"""Check that a UR Cartesian home pose uses the Cartesian motion API."""
import unittest
import importlib
import sys
import types
from unittest.mock import Mock, patch

from config import home_position, travel_offset
from arm_methods.calculatePosition import calculatePosition


class ArmMotionTests(unittest.TestCase):
    def test_taught_tip_height_is_never_crossed(self):
        fake_module = types.ModuleType("arm_methods.robotiq_two_finger_gripper")
        fake_module.Robotiq_Two_Finger_Gripper = Mock()
        with patch.dict(sys.modules, {fake_module.__name__: fake_module}):
            move_piece_module = importlib.import_module("arm_methods.movePiece")
        robot = Mock()
        a8 = [0.2, -0.3, 0.11, 0, 3.14, 0]
        h8 = [0.2, 0.0, 0.12, 0, 3.14, 0]
        a1 = [0.5, -0.3, 0.115, 0, 3.14, 0]
        for piece in ("P", "R", "N", "B", "Q", "K"):
            source, target = calculatePosition(piece, a8, h8, [0, 0], [7, 7], a1)
            self.assertGreaterEqual(min(source[2], target[2]), a8[2] - 1e-6)
            move_piece_module.movePiece(robot, source, target, minimum_tcp_z=a8[2])
        self.assertTrue(all(call.args[0][2] >= a8[2] - 1e-6 for call in robot.movel.call_args_list))
        robot.reset_mock()
        with self.assertRaisesRegex(ValueError, "below the taught"):
            move_piece_module.movePiece(robot, a8, [0.3, 0, 0.10, 0, 3.14, 0], minimum_tcp_z=a8[2])
        robot.movel.assert_not_called()

    def test_return_home_crosses_at_clearance_height(self):
        fake_module = types.ModuleType("arm_methods.robotiq_two_finger_gripper")
        fake_module.Robotiq_Two_Finger_Gripper = Mock()
        with patch.dict(sys.modules, {fake_module.__name__: fake_module}):
            move_piece_module = importlib.import_module("arm_methods.movePiece")
        robot = Mock()
        source = [0.30, -0.20, 0.19, 0, 3.14, 0]
        target = [0.35, -0.20, 0.19, 0, 3.14, 0]
        move_piece_module.movePiece(robot, source, target, minimum_tcp_z=0.18)
        poses = [call.args[0] for call in robot.movel.call_args_list]
        self.assertEqual(poses[-2][:2], home_position[:2])
        self.assertAlmostEqual(poses[-2][2], 0.19 + travel_offset)
        self.assertEqual(poses[-1], home_position)

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
