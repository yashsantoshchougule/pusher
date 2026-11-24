# JB-07 — Add Step can create a duplicate or unusable step

Should Fix · [API Journey Builder issue index](https://docs.google.com/document/d/1RQ0TIbYY5YRb_o6wu8lIkEKrgnYX_C_rEoGiE2UlP6E/edit?usp=drivesdk)

## Implementation prompt

Make Add Step produce a unique stable ID after deletion, reordering or rapid clicks. The previous ID was based on list length, so deleting a middle step could make the next ID collide. The new step also used a sandbox path that does not exist and a token placeholder the user might never extract.

1. Assign a fresh ID per click and calculate the human-readable name from the latest list. Keep existing saved IDs stable.
2. Use a safe method and neutral headers. Start live steps with a root-relative path and sandbox steps with the built-in catalog path.
3. Test delete then add, repeated add from one render, and sandbox and live defaults. Keep ten-step enforcement and persisted identity unchanged. Run Journey Builder tests.

## Verification

16 Node tests passed in the builder and Traffic Setup fixtures, including delete and re-add, rapid add, and sandbox defaults. [Drive report](https://docs.google.com/document/d/1azAtJ6Ydcyjv1NCEXTrztm_eIkHksQqRGtxazU4Q9fQ/edit?usp=drivesdk)
