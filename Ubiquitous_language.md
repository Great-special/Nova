# Ubiquitous Language

This project is Nova, a voice assistant that waits for a wake word, captures a command, routes it, and speaks back.

## Voice Flow

- **Wake word**: The phrase that activates Nova. It is configured as `WAKE_WORD`.
- **Wake utterance**: The full bit of speech Nova hears while waiting for the wake word.
- **Immediate command**: A command spoken in the same utterance as the wake word. Example: `nova open chrome`.
- **Follow-up command**: A command spoken after Nova hears the wake word and asks, "Yes? I'm listening."
- **Command**: The user request sent to the router. It should not include the wake word.
- **Route**: The step that decides whether a command belongs to a local skill or the AI brain.
- **Response**: The text Nova speaks after a command is handled.

## Wake-Word Rules

- If Nova hears only the wake word, it asks for a follow-up command.
- If Nova hears the wake word plus more speech, it treats the remaining speech as the immediate command.
- If Nova hears speech without the wake word, it keeps waiting.
