# Product brief

## Who and what

HomePilot helps one household keep a simple grocery inventory and shopping list. In the MVP, a person uses a desktop web page and webcam to capture a grocery item, reviews a model suggestion, and confirms what to save. iPhone capture follows after this desktop flow works. They can inspect inventory and ask a text assistant to add or review grocery-list items.

## Core jobs

1. **Remember what we have.** A confirmed product and quantity appear in inventory and remain after reload.
2. **Reduce typing.** A photo supplies a candidate name; the user can correct it or enter an unknown product manually.
3. **Make a useful shopping list.** A text request can inspect inventory and add an item through a runtime MCP tool, with the result visible in the list.

## Product principles

- The user remains the authority on product identity and quantity.
- An honest unknown result is better than a confident wrong item.
- A short, reliable end-to-end demo is more valuable than many disconnected features.
- The robot is a future interface to the same application, after the software works.

## Demo story

Capture a grocery item with a desktop webcam; review or correct the prediction; save one unit; reload and see it in inventory; ask HomePilot to add another item to the grocery list; see the list update. The demo should also show an unknown photo and manual correction.

Acceptance criteria and exclusions are in [MVP_SCOPE.md](MVP_SCOPE.md).
