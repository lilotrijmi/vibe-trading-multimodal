# Attachment Strip Above Composer — Design

## Context

On narrow mobile screens, image and URL attachment UI currently renders inside the rounded chat composer between the `+` menu and the textarea. A selected image or URL therefore consumes the text-entry width and makes it unclear where the user should type.

Ordinary uploaded files already render above the composer. The fix should align multimodal attachments with that existing pattern without changing attachment behavior.

## Approved UX

Use a compact attachment strip directly above the chatbox.

- Image and URL attachment chips render above the rounded composer.
- The URL entry row, upload/loading state, and multimodal errors render in the same strip.
- The attachment remains visible, identifiable, and removable.
- The textarea keeps its full available width.
- The `+` menu, textarea, and send/stop button remain inside the rounded composer.
- The behavior is consistent on mobile and desktop.

## Architecture

Keep `MultimodalAttachment` as the owner of all multimodal state and behavior:

- image selection and upload;
- pasted-image handling;
- URL entry and validation;
- local preview state;
- removal and object-URL cleanup;
- upload and validation errors;
- global `multimodal:open-image`, `multimodal:show-url`, and `multimodal:paste-image` event handling;
- synchronization to `Agent` through the existing `onChange` callback.

Only relocate the existing `<MultimodalAttachment />` instance in `frontend/src/pages/Agent.tsx`. Do not lift state, add context, introduce new event types, or alter upload/send code.

## Component Placement

Current order:

1. ordinary file attachment chip;
2. upload indicator;
3. runtime controls;
4. rounded composer containing `+`, `MultimodalAttachment`, textarea, and send;
5. secondary export row.

New order:

1. ordinary file attachment chip;
2. upload indicator;
3. `MultimodalAttachment` full-width strip;
4. runtime controls;
5. rounded composer containing only `+`, textarea, and send;
6. secondary export row.

The existing empty secondary-toolbar placeholder and its stale comment should be removed or corrected. The multimodal component must appear once in the DOM and before the rounded composer.

## Responsive Behavior

No separate mobile implementation is needed. The existing chip already uses `max-w-full`, truncation, and compact sizing. Moving it into a full-width vertical form stack gives it enough width on mobile while preserving desktop behavior.

The attachment strip should use `min-w-0`/full-width containment where needed so long URLs and filenames truncate rather than overflow.

## Accessibility and Error Handling

- Preserve existing remove button labels and keyboard behavior.
- Preserve auto-focus and Enter/Escape behavior in the URL editor.
- Preserve current image alt text.
- Preserve loading/error rendering and do not silently hide errors.
- Do not duplicate hidden file inputs or event listeners.

## Testing

Add focused rendering coverage that verifies:

1. multimodal attachment UI is mounted once;
2. its attachment strip appears before the composer in DOM order;
3. the composer still contains the `+` trigger, textarea, and send button;
4. multimodal UI is not a descendant of the rounded composer;
5. existing image/URL trigger and clear behavior remains unchanged where practical.

Run TypeScript checking, focused frontend tests, and the production frontend build. Existing unrelated Settings test failures should be reported separately rather than attributed to this layout-only change.

## Scope

This change is visual relocation only. It must not modify:

- API requests;
- accepted file types or limits;
- image upload processing;
- paste interception;
- URL validation/fetching;
- attachment removal semantics;
- prompt construction;
- send-button enablement;
- post-send cleanup.
