from typing import TYPE_CHECKING
from typing import Optional
from typing import TypeVar
from typing import Union

import hikari

from miru.button import Button
from miru.context import ViewContext
from miru.modal import Modal
from miru.text_input import TextInput

if TYPE_CHECKING:
    from . import AiryPages

AiryPagesT = TypeVar("AiryPagesT", bound="AiryPages")


class NavButton(Button):
    """A baseclass for all navigation buttons. NavigatorView requires instances of this class as it's items.

    Parameters
    ----------
    style : Union[hikari.ButtonStyle, int], optional
        The style of the navigation button, by default hikari.ButtonStyle.PRIMARY
    label : Optional[str], optional
        The label of the navigation button, by default None
    disabled : bool, optional
        Boolean indicating if the navigation button is disabled, by default False
    custom_id : Optional[str], optional
        The custom identifier of the navigation button, by default None
    emoji : Union[hikari.Emoji, str, None], optional
        The emoji of the navigation button, by default None
    row : Optional[int], optional
        The row this navigation button should occupy. Leave None for auto-placement.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.PRIMARY,
        label: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        row: Optional[int] = None,
    ):
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id=custom_id,
            url=None,
            emoji=emoji,
            row=row,
        )
        self.view: AiryPages


    @property
    def url(self) -> None:
        return None

    @url.setter
    def url(self, value: str) -> None:
        raise AttributeError("NavButton cannot have attribute url.")

    async def before_page_change(self) -> None:
        """
        Called when the navigator is about to transition to the next page. Also called before the first page is sent.
        """
        pass


# TODO: Add Custom Emojis for navigator buttons

class NextButton(NavButton):
    """
    A built-in NavButton to jump to the next page.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.PRIMARY,
        label: Optional[str] = "Next",
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        row: Optional[int] = None,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id, emoji=emoji, row=row)

    async def callback(self, context: ViewContext) -> None:
        self.view.current_page += 1
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page == self.view.source.get_max_pages() - 1:
            self.disabled = True
        else:
            self.disabled = False


class PrevButton(NavButton):
    """
    A built-in NavButton to jump to previous page.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.PRIMARY,
        label: Optional[str] = "Back",
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        row: Optional[int] = None,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id, emoji=emoji, row=row)

    async def callback(self, context: ViewContext) -> None:
        self.view.current_page -= 1
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page == 0:
            self.disabled = True
        else:
            self.disabled = False


class FirstButton(NavButton):
    """
    A built-in NavButton to jump to first page.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.PRIMARY,
        label: Optional[str] = '≪',
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        row: Optional[int] = None,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id, emoji=emoji, row=row)

    async def callback(self, context: ViewContext) -> None:
        self.view.current_page = 0
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page == 0:
            self.disabled = True
        else:
            self.disabled = False


class LastButton(NavButton):
    """
    A built-in NavButton to jump to the last page.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.PRIMARY,
        label: Optional[str] = '≫',
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        row: Optional[int] = None,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id, emoji=emoji, row=row)

    async def callback(self, context: ViewContext) -> None:
        self.view.current_page = self.view.source.get_max_pages() - 1
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page == self.view.source.get_max_pages() - 1:
            self.disabled = True
        else:
            self.disabled = False


class IndicatorButton(NavButton):
    """
    A built-in NavButton to show the current page's number.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.SECONDARY,
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        disabled: bool = False,
        row: Optional[int] = None,
    ):
        # Either label or emoji is required, so we pass a placeholder
        super().__init__(style=style, label="0/0", custom_id=custom_id, emoji=emoji, disabled=disabled, row=row)

    async def before_page_change(self) -> None:
        self.label = f"{self.view.current_page+1}/{self.view.source.get_max_pages()}"

    async def callback(self, context: ViewContext) -> None:
        modal = Modal("Jump to page", autodefer=False)
        modal.add_item(TextInput(label="Page Number", placeholder="Enter a page number to jump to it..."))
        await context.respond_with_modal(modal)
        await modal.wait()

        if not modal.values:
            return

        try:
            page_number = int(list(modal.values.values())[0]) - 1
        except (ValueError, TypeError):
            self.view._inter = modal.get_response_context().interaction
            return await modal.get_response_context().defer()

        self.view.current_page = page_number
        await self.view.send_page(modal.get_response_context())


class StopButton(NavButton):
    """
    A built-in NavButton to stop the navigator and disable all buttons.
    """

    def __init__(
        self,
        *,
        style: Union[hikari.ButtonStyle, int] = hikari.ButtonStyle.DANGER,
        label: Optional[str] = 'Quit',
        custom_id: Optional[str] = None,
        emoji: Union[hikari.Emoji, str, None] = None,
        row: Optional[int] = None,
    ):
        super().__init__(style=style, label=label, custom_id=custom_id, emoji=emoji, row=row)

    async def callback(self, context: ViewContext) -> None:
        if not self.view.message and not self.view.inter:
            return

        for button in self.view.children:
            assert isinstance(button, NavButton)
            button.disabled = True

        if self.view.inter and self.view.ephemeral:
            await self.view.inter.edit_initial_response(components=self.view.build())
        elif self.view.message:
            await self.view.message.edit(components=self.view.build())
        self.view.stop()
