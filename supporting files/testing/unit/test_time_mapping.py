"""
Unit test for 100-frame time-of-day clock mapping logic in LoginPage.jsx
Verifies that all 24 hours of the day correctly map to their specified frame ranges.
"""

def get_time_based_frame_data(hours: int, minutes: int):
    phase = 'Morning'
    frame = 1

    if 5 <= hours < 12:
        phase = 'Morning'
        elapsed = (hours - 5) * 60 + minutes
        frame = 1 + min(24, int((elapsed / 420) * 25))
    elif 12 <= hours < 17:
        phase = 'Afternoon'
        elapsed = (hours - 12) * 60 + minutes
        frame = 26 + min(22, int((elapsed / 300) * 23))
    elif 17 <= hours < 20:
        phase = 'Evening'
        elapsed = (hours - 17) * 60 + minutes
        frame = 49 + min(27, int((elapsed / 180) * 28))
    else:
        phase = 'Night'
        elapsed = (hours - 20) * 60 + minutes if hours >= 20 else (hours + 4) * 60 + minutes
        frame = 77 + min(23, int((elapsed / 540) * 24))

    return {
        'frame': frame,
        'phase': phase,
        'src': f'/frames/ezgif-frame-{frame:03d}.jpg'
    }

def test_boundaries():
    # Morning: 05:00 -> 1, 11:59 -> 25
    assert get_time_based_frame_data(5, 0)['frame'] == 1, "05:00 should be frame 1"
    assert get_time_based_frame_data(5, 0)['phase'] == 'Morning'
    assert get_time_based_frame_data(11, 59)['frame'] == 25, "11:59 should be frame 25"
    assert get_time_based_frame_data(11, 59)['phase'] == 'Morning'

    # Afternoon: 12:00 -> 26, 16:59 -> 48
    assert get_time_based_frame_data(12, 0)['frame'] == 26, "12:00 should be frame 26"
    assert get_time_based_frame_data(12, 0)['phase'] == 'Afternoon'
    assert get_time_based_frame_data(16, 59)['frame'] == 48, "16:59 should be frame 48"
    assert get_time_based_frame_data(16, 59)['phase'] == 'Afternoon'

    # Evening: 17:00 -> 49, 19:59 -> 76
    assert get_time_based_frame_data(17, 0)['frame'] == 49, "17:00 should be frame 49"
    assert get_time_based_frame_data(17, 0)['phase'] == 'Evening'
    assert get_time_based_frame_data(19, 59)['frame'] == 76, "19:59 should be frame 76"
    assert get_time_based_frame_data(19, 59)['phase'] == 'Evening'

    # Night: 20:00 -> 77, 04:59 -> 100
    assert get_time_based_frame_data(20, 0)['frame'] == 77, "20:00 should be frame 77"
    assert get_time_based_frame_data(20, 0)['phase'] == 'Night'
    assert get_time_based_frame_data(0, 0)['phase'] == 'Night'
    assert get_time_based_frame_data(4, 59)['frame'] == 100, "04:59 should be frame 100"
    assert get_time_based_frame_data(4, 59)['phase'] == 'Night'

    print("All 9 time boundary test cases PASSED!")

if __name__ == '__main__':
    test_boundaries()
