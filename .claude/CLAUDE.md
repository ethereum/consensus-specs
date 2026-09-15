## Structure

- Specs are markdown; executable Python is generated from them.
- Each spec states only what it changes; the rest is inherited.
- Changes to old specs may require matching updates to newer ones.
- Presets are comptime; configs are runtime.

## Constraints

- Do not edit generated Python spec files.
- Do not assume how the specs behave, as they are evolving.
- Do not change stable spec behavior without explicit permission.
