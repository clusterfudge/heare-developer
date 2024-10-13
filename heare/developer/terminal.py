from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, TextArea, Button, Static
from textual.reactive import reactive
from textual.binding import Binding
from textual.widgets import ListItem, ListView
from heare.developer.terminal_user_interface import (
    TerminalUserInterface,
    Sidebar as ToolSidebar,
)
from heare.developer.sandbox import SandboxMode


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


class MainContent(Container):
    """The main content area with chat history and sidebar."""

    show_sidebar = reactive(False)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield ChatHistory(id="chat-history", classes="pane")
            yield ToolSidebar(classes="sidebar")

    def on_mount(self) -> None:
        self.update_layout()

    def update_layout(self) -> None:
        sidebar = self.query_one(ToolSidebar)
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
        self.user_interface = TerminalUserInterface(
            self, SandboxMode.REMEMBER_PER_RESOURCE
        )

    def compose(self) -> ComposeResult:
        yield Header()
        yield MainContent()
        yield Footer()
        yield TextArea(id="input")

    def on_mount(self) -> None:
        self.query_one(TextArea).focus()
        self.user_interface.display_welcome_message()

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

        # Check if we're waiting for user input
        if self.user_interface.waiting_for_input:
            self.user_interface.user_input = current_text.strip()
            self.user_interface.waiting_for_input = False

    def send_message(self, message: str) -> None:
        if message:
            self.user_interface.handle_user_input(message)
            # Here you would typically call your agent to process the message
            # For example: response = run_agent(message, self.user_interface)

    def append_to_conversation(self, message_type: str, content: str) -> None:
        chat_history = self.query_one("#chat-history", ChatHistory)
        new_message = ChatMessage(message_type, content)
        chat_history.add_message(new_message)
        chat_history.scroll_end(animate=False)

    def action_toggle_sidebar(self) -> None:
        main_content = self.query_one(MainContent)
        main_content.toggle_sidebar()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-tool-usage":
            self.user_interface.permission_result = True
            self.user_interface.waiting_for_permission = False
        elif event.button.id == "deny-tool-usage":
            self.user_interface.permission_result = False
            self.user_interface.waiting_for_permission = False

    def update_tool_usage(self, content: str) -> None:
        tool_usage_area = self.query_one("#tool-usage-area")
        tool_usage_area.load_text(content)

    def update_tool_result(self, content: str) -> None:
        tool_result_content = self.query_one("#tool-result-content")
        tool_result_content.update(content)

    def show_sidebar(self, tab: str = "Tool Usage") -> None:
        main_content = self.query_one(MainContent)
        main_content.show_sidebar = True
        main_content.update_layout()
        tabbed_content = self.query_one(ToolSidebar).query_one("TabbedContent")
        tabbed_content.active = tab


def main():
    app = ChatbotApp()
    app.run()


if __name__ == "__main__":
    main()
