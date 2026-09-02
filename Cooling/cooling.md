# Cooling

← [Back to README](../README.md)

*This is a V2 full sleeper concern. V1 keeps the candidate's own cooling solution.*

The second major unsolved problem for the full sleeper build. Modern gaming laptop TDPs are just not the same as what the T60 chassis was designed to breathe for, so some chassis modifications are almost certainly unavoidable.

## Airflow

The T60's original cooling vents are in fixed positions and sized for a much lower TDP. It's pretty much a given that some drilling or cutting will be needed to get adequate airflow for a modern board. The goal for V2 is to keep this as invisible as possible from the outside, but it's hard to see how it gets avoided entirely.

## Custom Cooling Solution

Designing a custom cooling solution from scratch using heat pipes is a significant engineering task. A potentially simpler approach is to frankenstein the original T60 cooler with the candidate board's cold plate — reuse the T60's heat pipe routing but swap the contact plate for one that matches the candidate's die layout. The downside is it takes up more space than a clean custom design.

## How to Approach It

The most sensible path when this stage is reached is probably to do a 3D scan of both the T60 chassis internals and the candidate board, then try to make everything fit in CAD before committing to any physical modifications. That way the viability can be checked before anything gets cut.

## Status

Not started. Blocked on having a candidate board in hand and the power delivery problem being solved first.
