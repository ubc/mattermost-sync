from ddt import ddt, data, unpack
import unittest

from mattermostsync import parse_course


@ddt
class TestStringMethods(unittest.TestCase):

    @data(
        ['CPSC_101_102_2018W', [[('CPSC_101_102_2018W', 'UBC')], 'CPSC10110218W']],
        ['CPSC_101_102_2018WO', [[('CPSC_101_102_2018W', 'UBCO')], 'CPSC10110218WO']],
        ['CPSC_101_102_2018W=MY_TEAM', [[('CPSC_101_102_2018W', 'UBC')], 'MY_TEAM']],
        [
            'CPSC_101_102_2018W+CPSC_102_102_2018WO=MY_TEAM',
            [[('CPSC_101_102_2018W', 'UBC'), ('CPSC_102_102_2018W', 'UBCO')], 'MY_TEAM']
        ],
    )
    @unpack
    def test_parse_course(self, course, result):
        courses, team = parse_course(course)
        self.assertEqual(result[0], courses)
        self.assertEqual(result[1], team)

    @data(
        ['CPSC_101_102_2018W=M'],
        ['CPSC_101_102_2018W=CPSC=CPSC_102']
    )
    @unpack
    def test_exception_parse_course(self, course):
        with self.assertRaises(ValueError):
            parse_course(course)


if __name__ == '__main__':
    unittest.main()
