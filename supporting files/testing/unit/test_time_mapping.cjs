/**
 * Automated Unit Test for Time-to-Frame Mapping Logic
 * Run with: node "supporting files/testing/unit/test_time_mapping.cjs"
 */

function getTimeBasedFrameData(hours, minutes) {
  let frame = 1;
  let phase = 'Morning';

  if (hours >= 5 && hours < 12) {
    phase = 'Morning';
    const elapsed = (hours - 5) * 60 + minutes;
    frame = 1 + Math.min(24, Math.floor((elapsed / 420) * 25));
  } else if (hours >= 12 && hours < 17) {
    phase = 'Afternoon';
    const elapsed = (hours - 12) * 60 + minutes;
    frame = 26 + Math.min(22, Math.floor((elapsed / 300) * 23));
  } else if (hours >= 17 && hours < 20) {
    phase = 'Evening';
    const elapsed = (hours - 17) * 60 + minutes;
    frame = 49 + Math.min(27, Math.floor((elapsed / 180) * 28));
  } else {
    phase = 'Night';
    const elapsed = hours >= 20 ? (hours - 20) * 60 + minutes : (hours + 4) * 60 + minutes;
    frame = 77 + Math.min(23, Math.floor((elapsed / 540) * 24));
  }

  const paddedFrame = String(frame).padStart(3, '0');
  return {
    frame,
    phase,
    src: `/frames/ezgif-frame-${paddedFrame}.jpg`,
  };
}

const testCases = [
  { hours: 5, minutes: 0, expectedFrame: 1, expectedPhase: 'Morning' },
  { hours: 11, minutes: 59, expectedFrame: 25, expectedPhase: 'Morning' },
  { hours: 12, minutes: 0, expectedFrame: 26, expectedPhase: 'Afternoon' },
  { hours: 16, minutes: 59, expectedFrame: 48, expectedPhase: 'Afternoon' },
  { hours: 17, minutes: 0, expectedFrame: 49, expectedPhase: 'Evening' },
  { hours: 19, minutes: 59, expectedFrame: 76, expectedPhase: 'Evening' },
  { hours: 20, minutes: 0, expectedFrame: 77, expectedPhase: 'Night' },
  { hours: 23, minutes: 59, expectedFrame: 87, expectedPhase: 'Night' },
  { hours: 0, minutes: 0, expectedFrame: 87, expectedPhase: 'Night' },
  { hours: 4, minutes: 59, expectedFrame: 100, expectedPhase: 'Night' },
];

let failed = 0;
testCases.forEach((tc) => {
  const res = getTimeBasedFrameData(tc.hours, tc.minutes);
  const ok = res.frame === tc.expectedFrame && res.phase === tc.expectedPhase;
  if (!ok) {
    console.error(`FAIL: ${tc.hours}:${tc.minutes} expected frame ${tc.expectedFrame} (${tc.expectedPhase}), got ${res.frame} (${res.phase})`);
    failed++;
  } else {
    console.log(`PASS: ${String(tc.hours).padStart(2, '0')}:${String(tc.minutes).padStart(2, '0')} -> Frame ${res.frame} (${res.phase})`);
  }
});

if (failed === 0) {
  console.log('\nAll 10 boundary tests passed successfully!');
} else {
  process.exit(1);
}
