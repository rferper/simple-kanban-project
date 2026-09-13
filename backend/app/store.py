"""Persistence — the mock database.

`Store` is the whole storage surface the rest of the backend is allowed to use.
`InMemoryStore` is today's implementation: a few dicts. When a real database
arrives it implements this same Protocol and is swapped in through
`app.dependencies.get_store`; nothing in `app/service.py`, `app/auth.py` or the
routers changes.

Two disciplines the mock imposes on purpose, because a real database imposes
them too:

* **Stored objects are copied on the way in and on the way out.** A caller
  holding a `Card` cannot mutate what is stored by editing it.
* **Nothing is ordered by accident.** `list_cards` returns insertion order.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.models import Card, Preferences, TokenSession, User


@runtime_checkable
class Store(Protocol):
    # cards
    def list_cards(self) -> list[Card]: ...

    def get_card(self, card_id: str) -> Card | None: ...

    def save_card(self, card: Card) -> Card: ...

    def delete_card(self, card_id: str) -> bool: ...

    # preferences
    def get_preferences(self) -> Preferences: ...

    def save_preferences(self, preferences: Preferences) -> Preferences: ...

    # users
    def get_user(self, user_id: str) -> User | None: ...

    def get_user_by_email(self, email: str) -> User | None: ...

    def save_user(self, user: User) -> User: ...

    # tokens
    def get_token(self, token: str) -> TokenSession | None: ...

    def save_token(self, token: str, user_id: str, expires_at: datetime) -> TokenSession: ...

    def delete_token(self, token: str) -> bool: ...

    def delete_tokens_for(self, user_id: str) -> int: ...


class InMemoryStore:
    """The mock database. Lives for as long as the process does."""

    def __init__(
        self,
        cards: list[Card] | None = None,
        preferences: Preferences | None = None,
        users: list[User] | None = None,
    ) -> None:
        self._cards: dict[str, Card] = {}
        for card in cards or []:
            self._cards[card.id] = card.model_copy(deep=True)

        self._preferences = (preferences or Preferences()).model_copy(deep=True)

        self._users: dict[str, User] = {}
        for user in users or []:
            self._users[user.id] = user.model_copy(deep=True)

        self._tokens: dict[str, TokenSession] = {}

    @classmethod
    def seeded(cls) -> InMemoryStore:
        """Loaded with the fixtures from `_docs/specs.md` §31 and the demo account."""
        from app.auth import build_demo_user
        from app.seed import build_seed

        cards, preferences = build_seed()
        return cls(cards=cards, preferences=preferences, users=[build_demo_user()])

    # ------------------------------------------------------------------ cards

    def list_cards(self) -> list[Card]:
        return [card.model_copy(deep=True) for card in self._cards.values()]

    def get_card(self, card_id: str) -> Card | None:
        card = self._cards.get(card_id)
        return card.model_copy(deep=True) if card else None

    def save_card(self, card: Card) -> Card:
        self._cards[card.id] = card.model_copy(deep=True)
        return card.model_copy(deep=True)

    def delete_card(self, card_id: str) -> bool:
        return self._cards.pop(card_id, None) is not None

    # ------------------------------------------------------------ preferences

    def get_preferences(self) -> Preferences:
        return self._preferences.model_copy(deep=True)

    def save_preferences(self, preferences: Preferences) -> Preferences:
        self._preferences = preferences.model_copy(deep=True)
        return self._preferences.model_copy(deep=True)

    # ------------------------------------------------------------------ users

    def get_user(self, user_id: str) -> User | None:
        user = self._users.get(user_id)
        return user.model_copy(deep=True) if user else None

    def get_user_by_email(self, email: str) -> User | None:
        wanted = email.strip().lower()
        for user in self._users.values():
            if user.email.lower() == wanted:
                return user.model_copy(deep=True)
        return None

    def save_user(self, user: User) -> User:
        self._users[user.id] = user.model_copy(deep=True)
        return user.model_copy(deep=True)

    # ----------------------------------------------------------------- tokens

    def get_token(self, token: str) -> TokenSession | None:
        session = self._tokens.get(token)
        return session.model_copy(deep=True) if session else None

    def save_token(self, token: str, user_id: str, expires_at: datetime) -> TokenSession:
        session = TokenSession(token=token, user_id=user_id, expires_at=expires_at)
        self._tokens[token] = session
        return session.model_copy(deep=True)

    def delete_token(self, token: str) -> bool:
        return self._tokens.pop(token, None) is not None

    def delete_tokens_for(self, user_id: str) -> int:
        doomed = [t for t, s in self._tokens.items() if s.user_id == user_id]
        for token in doomed:
            del self._tokens[token]
        return len(doomed)
