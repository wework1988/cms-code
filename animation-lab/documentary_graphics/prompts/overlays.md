# Cinematic overlay planning

Read the shared policy first.

Supported treatments: location_callout, detail_spotlight, key_fact, evidence_inset, route_direction, measurement.

You may say that a callout needs an object target. You may not supply the target coordinates.
manual_anchor requires keyframes from a person or a tracker. tracked_anchor and scene_aligned are unsupported and must not be downgraded to a fixed point.
A route needs supplied screen points. An arrow is only for a real direction.
A measurement needs two supplied points plus a value and a unit that the story already gives. Do not convert pixels into metres.
An evidence inset needs a file that already exists and a source label. Do not describe a document that was not supplied.

The label position and the object anchor are different. Keep the label still when the anchor moves.
Do not draw a keyframe across a scene cut.
