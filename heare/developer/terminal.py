from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, TextArea, Button, Static, Input
from textual.reactive import reactive
from textual.binding import Binding
from textual.widgets import ListItem, ListView


class ChatMessage(Static):
    """A widget to display a single chat message."""

    def __init__(self, message_type: str, content: str):
        super().__init__()
        self.message_type = message_type
        self.content = content

    def render(self) -> str:
        if self.message_type == "human":
            return f"[bold blue]Human:[/bold blue] {self.content}"
        elif self.message_type == "assistant":
            return f"[bold green]Assistant:[/bold green] {self.content}"
        elif self.message_type == "tool_usage":
            return f"[bold yellow]Tool Usage:[/bold yellow] {self.content}"
        else:
            return f"[bold]{self.message_type}:[/bold] {self.content}"


class ChatHistory(ListView):
    """A ListView to display chat messages."""

    def on_mount(self):
        self.can_focus = True

    def add_message(self, message: ChatMessage):
        list_item = ListItem(ChatMessage(message.message_type, message.content))
        list_item.add_class(message.message_type)
        self.append(list_item)
        self.clear_highlight()

    def on_focus(self) -> None:
        if not self.app.query_one(MainContent).show_sidebar:
            self.clear_highlight()

    def on_blur(self) -> None:
        self.clear_highlight()

    def clear_highlight(self) -> None:
        self.highlighted = None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not self.app.query_one(MainContent).show_sidebar:
            event.prevent_default()
            self.clear_highlight()


class Sidebar(Container):
    """An interactive sidebar."""

    def compose(self) -> ComposeResult:
        yield Button("Clear History", id="clear-history")
        yield Button("Inject Assistant Message", id="inject-assistant")
        yield Button("Inject Tool Usage", id="inject-tool")
        yield Input(placeholder="Content", id="inject-content")


class MainContent(Container):
    """The main content area with chat history and sidebar."""

    show_sidebar = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield ChatHistory(id="chat-history", classes="pane")
            yield Sidebar(classes="sidebar")

    def on_mount(self) -> None:
        self.update_layout()

    def update_layout(self) -> None:
        sidebar = self.query_one(Sidebar)
        sidebar.set_class(not self.show_sidebar, "hidden")
        self.query_one(ChatHistory).clear_highlight()

    def toggle_sidebar(self) -> None:
        self.show_sidebar = not self.show_sidebar
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
    #chat-history {
        background: $surface;
        overflow-y: auto;
        width: 3fr;
    }
    .sidebar {
        width: 1fr;
        background: $panel;
        padding: 1;
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
    Button {
        width: 100%;
        margin-bottom: 1;
    }
    Input {
        margin-bottom: 1;
    }
    #chat-history > ListItem {
        padding: 0 1;
        margin: 1 0;
        border: solid transparent;
    }
    #chat-history > ListItem.human {
        border: solid #3498db;
    }
    #chat-history > ListItem.assistant {
        border: solid #2ecc71;
    }
    #chat-history > ListItem.tool_usage {
        border: solid #f1c40f;
    }
    #chat-history:focus > ListItem.--highlight {
        background: #2c3e50;
    }
    """

    BINDINGS = [
        Binding("ctrl+s", "toggle_sidebar", "Toggle Sidebar"),
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
        current_text = input_area.text

        if current_text.startswith("{") and not self.multiline_mode:
            self.multiline_mode = True
            input_area.add_class("multiline")
        elif self.multiline_mode and current_text.endswith("}\n"):
            self.multiline_mode = False
            input_area.remove_class("multiline")
            self.send_message(current_text[1:-2].strip())  # Remove braces and newline
            input_area.clear()
        elif not self.multiline_mode and current_text.endswith("\n"):
            # Single line mode, user pressed enter
            self.send_message(current_text.strip())
            input_area.clear()

    def send_message(self, message: str) -> None:
        if message:
            self.append_to_conversation("human", message)

    def append_to_conversation(self, message_type: str, content: str) -> None:
        chat_history = self.query_one("#chat-history", ChatHistory)
        new_message = ChatMessage(message_type, content)
        chat_history.add_message(new_message)
        chat_history.scroll_end(animate=False)

    def action_toggle_sidebar(self) -> None:
        main_content = self.query_one(MainContent)
        main_content.toggle_sidebar()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "clear-history":
            self.clear_history()
        elif event.button.id == "inject-assistant":
            content = self.query_one("#inject-content", Input).value
            if content:
                self.inject_message("assistant", content)
                self.query_one("#inject-content", Input).value = ""
        elif event.button.id == "inject-tool":
            content = self.query_one("#inject-content", Input).value
            if content:
                self.inject_message("tool_usage", content)
                self.query_one("#inject-content", Input).value = ""

    def clear_history(self) -> None:
        chat_history = self.query_one("#chat-history", ChatHistory)
        chat_history.clear()

    def inject_message(self, message_type: str, content: str) -> None:
        self.append_to_conversation(message_type, content)

    def override_history(self, messages: list[tuple[str, str]]) -> None:
        chat_history = self.query_one("#chat-history", ChatHistory)
        chat_history.clear()
        for message_type, content in messages:
            self.append_to_conversation(message_type, content)


def main():
    app = ChatbotApp()
    app.run()


if __name__ == "__main__":
    main()
