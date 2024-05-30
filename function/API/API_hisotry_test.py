import unittest

from function.API.API_history import APIHistoryFunction


class TestAPIHistoryFunction(unittest.TestCase):
    def test_get_trigger_time(self):
        # Setup
        api = APIHistoryFunction()
        data = [
            {"timestamp": 1000, "value": 3.0},
            {"timestamp": 2000, "value": 1.0},
            {"timestamp": 3000, "value": 1.0},
            {"timestamp": 4000, "value": 2.0},
            {"timestamp": 5000, "value": 1.0}
        ]
        trigger_value = '1'
        start = 1500
        stop = 6000

        # Execute
        result = APIHistoryFunction.get_trigger_time(trigger_value, start, stop, data)

        # Verify
        expected_result = {
            "trigger_times": 2,  # Since value '1' is seen first at 2000 and then at 5000
            "trigger_second": 3000  # Total time from first trigger at 2000 to 4000 and second at 5000 to 4500 (stop time)
        }
        self.assertEqual(result, expected_result)

        start = 2500
        stop = 4000

        # Execute
        result = APIHistoryFunction.get_trigger_time(trigger_value, start, stop, data)

        # Verify
        expected_result = {
            "trigger_times": 1,  # Since value '1' is seen first at 2000 and then at 5000
            "trigger_second": 1500  # Total time from first trigger at 2000 to 4000 and second at 5000 to 4500 (stop time)
        }
        self.assertEqual(result, expected_result)

        start = 0
        stop = 4500

        # Execute
        result = APIHistoryFunction.get_trigger_time(trigger_value, start, stop, data)

        # Verify
        expected_result = {
            "trigger_times": 1,  # Since value '1' is seen first at 2000 and then at 5000
            "trigger_second": 2000  # Total time from first trigger at 2000 to 4000 and second at 5000 to 4500 (stop time)
        }
        self.assertEqual(result, expected_result)

        start = 500
        stop = 1500

        # Execute
        result = APIHistoryFunction.get_trigger_time(trigger_value, start, stop, data)

        # Verify
        expected_result = {
            "trigger_times": 0,  # Since value '1' is seen first at 2000 and then at 5000
            "trigger_second": 0  # Total time from first trigger at 2000 to 4000 and second at 5000 to 4500 (stop time)
        }
        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main()
