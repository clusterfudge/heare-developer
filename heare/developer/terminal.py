from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, TextArea, Static
from textual.reactive import reactive
from textual.binding import Binding


class ChatMessage(Static):
    """A widget to display a single chat message."""


class MainContent(Container):
    """The main content area with horizontal split."""

    is_split = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Container(Static(id="chat-history"), classes="pane")
            yield Container(Static(id="dynamic-content"), classes="pane hidden")

    def on_mount(self) -> None:
        self.update_layout()

    def update_layout(self) -> None:
        dynamic_content = self.query_one("#dynamic-content")
        if self.is_split:
            dynamic_content.remove_class("hidden")
        else:
            dynamic_content.add_class("hidden")

    def toggle_split(self) -> None:
        self.is_split = not self.is_split
        self.update_layout()

    def remove_split(self):
        if self.is_split:
            self.is_split = False
            self.update_layout()


class ChatbotApp(App):
    """The main application class."""

    CSS = """
    MainContent {
        height: 1fr;
    }
    .pane {
        width: 1fr;
        height: 100%;
        border: solid $primary;
    }
    #chat-history, #dynamic-content {
        background: $surface;
    }
    #chat-history {
        overflow-y: auto;
    }
    .hidden {
        display: none;
    }
    #input {
        height: auto;
        min-height: 1;
        max-height: 10;
        border: solid $accent;
    }
    #input:focus {
        border: solid $secondary;
    }
    #input.multiline {
        border: solid $success;
    }
    Footer {
        height: auto;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "toggle_right_pane", "Toggle Right Pane"),
        Binding("ESC", "close_right_pane"),
    ]

    def __init__(self):
        super().__init__()
        self.multiline_mode = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield MainContent()
        yield Footer()
        yield TextArea(id="input")

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        input_area = event.text_area
        lines = input_area.text.split("\n")
        if len(lines) == 1 and lines[0] == "{":
            self.multiline_mode = True
            input_area.add_class("multiline")
        elif len(lines) > 1 and lines[-1] == "}":
            self.multiline_mode = False
            input_area.remove_class("multiline")
            self.send_message(input_area.text[1:-1].strip())  # Remove braces and send
            input_area.clear()

    def on_key(self, event) -> None:
        if event.key == "enter":
            input_area = self.query_one(TextArea)
            if not self.multiline_mode:
                self.send_message()
                event.prevent_default()
            elif input_area.text.endswith("\n}"):
                # Multiline input is complete
                self.send_message(
                    input_area.text[1:-2].strip()
                )  # Remove braces and last newline
                input_area.clear()
                self.multiline_mode = False
                input_area.remove_class("multiline")
                event.prevent_default()

    def send_message(self, message=None) -> None:
        input_area = self.query_one("#input", TextArea)
        if message is None:
            message = input_area.text.strip()
        if message:
            self.append_to_conversation("User", message)
            # Here you would typically send the message to your chatbot backend
            # and receive a response. For this example, we'll just echo the message.
            self.append_to_conversation("Bot", f"You said: {message}")
            input_area.clear()

    def append_to_conversation(self, sender: str, content: str) -> None:
        chat_history = self.query_one("#chat-history", Static)
        new_message = ChatMessage(f"{sender}: {content}")
        chat_history.mount(new_message)
        chat_history.scroll_end(animate=False)

    def action_toggle_right_pane(self) -> None:
        main_content = self.query_one(MainContent)
        main_content.toggle_split()

    def action_remove_right_pane(self) -> None:
        main_content = self.query_one(MainContent)
        main_content.remove_split()

    def add_right_pane_input(self, prompt: str):
        right_pane = self.query_one("#dynamic-content")
        input_area = TextArea(prompt, id="right-pane-input")
        right_pane.mount(input_area)
        input_area.focus()

        def on_input_submitted(message: str):
            # Process the input here
            right_pane.mount(Static(f"You entered: {message}"))
            input_area.remove()

        input_area.on_submit = on_input_submitted


def main():
    app = ChatbotApp()
    app.run()


if __name__ == "__main__":
    main()
