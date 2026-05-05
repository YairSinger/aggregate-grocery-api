import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from geoalchemy2 import Geography

class Base(DeclarativeBase):
    pass

class UnitOfMeasure(str, Enum):
    MASS = "MASS"
    VOLUME = "VOLUME"
    UNITS = "UNITS"

class Chain(Base):
    __tablename__ = "chains"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, unique=True)
    official_id = Column(String, nullable=False, unique=True) # e.g. "7290027600007" for Shufersal
    
    stores = relationship("Store", back_populates="chain")
    items = relationship("Item", back_populates="chain")

class Store(Base):
    __tablename__ = "stores"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chain_id = Column(UUID(as_uuid=True), ForeignKey("chains.id"), nullable=False)
    branch_id = Column(String, nullable=False) # Chain-specific branch ID
    name = Column(String, nullable=False)
    address = Column(String)
    location = Column(Geography(geometry_type="POINT", srid=4326))
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chain = relationship("Chain", back_populates="stores")
    prices = relationship("Price", back_populates="store")

    __table_args__ = (UniqueConstraint("chain_id", "branch_id", name="uq_chain_branch"),)

class Item(Base):
    __tablename__ = "items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chain_id = Column(UUID(as_uuid=True), ForeignKey("chains.id"), nullable=False)
    item_code = Column(String, nullable=False, index=True) # Normalized item code (GTIN or internal)
    name = Column(String, nullable=False)
    brand = Column(String)
    category = Column(String)
    unit_of_measure = Column(SAEnum(UnitOfMeasure), nullable=False)
    quantity = Column(Float, nullable=False) # e.g. 1.0 (Liters), 500.0 (grams)

    chain = relationship("Chain", back_populates="items")
    prices = relationship("Price", back_populates="item")

    __table_args__ = (UniqueConstraint("chain_id", "item_code", name="uq_chain_item"),)

class Price(Base):
    __tablename__ = "prices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=False)
    base_price = Column(Numeric(precision=10, scale=2), nullable=False)
    discount_price = Column(Numeric(precision=10, scale=2)) # Price after standard discount
    effective_price = Column(Numeric(precision=10, scale=2), nullable=False) # Resulting price after thresholds met
    discount_description = Column(Text)
    price_per_unit = Column(Numeric(precision=12, scale=4), nullable=False) # Price / quantity
    
    item = relationship("Item", back_populates="prices")
    store = relationship("Store", back_populates="prices")

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=True) # Optional for test-only registration
    preferred_location = Column(Geography(geometry_type="POINT", srid=4326))

    aggregates = relationship("Aggregate", back_populates="user")
    shopping_lists = relationship("ShoppingList", back_populates="user")

class Aggregate(Base):
    __tablename__ = "aggregates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    unit_of_measure = Column(SAEnum(UnitOfMeasure), nullable=False)
    
    user = relationship("User", back_populates="aggregates")
    items = relationship("AggregateItem", back_populates="aggregate")

class AggregateItem(Base):
    __tablename__ = "aggregate_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_id = Column(UUID(as_uuid=True), ForeignKey("aggregates.id"), nullable=False)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    
    aggregate = relationship("Aggregate", back_populates="items")
    item = relationship("Item")
    
    # Ensures a user cannot have the same item in multiple aggregates
    # Note: Complex constraint, better handled in app logic or via user_id lookup
    __table_args__ = (UniqueConstraint("aggregate_id", "item_id", name="uq_aggregate_item"),)

class ShoppingList(Base):
    __tablename__ = "shopping_lists"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="shopping_lists")
    entries = relationship("ShoppingListEntry", back_populates="shopping_list")

class ShoppingListEntry(Base):
    __tablename__ = "shopping_list_entries"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shopping_list_id = Column(UUID(as_uuid=True), ForeignKey("shopping_lists.id"), nullable=False)
    aggregate_id = Column(UUID(as_uuid=True), ForeignKey("aggregates.id"), nullable=True)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=True)
    desired_amount = Column(Float, nullable=False)

    shopping_list = relationship("ShoppingList", back_populates="entries")
    aggregate = relationship("Aggregate")
    item = relationship("Item")


# ---------------------------------------------------------------------------
# Agent ordering models
# ---------------------------------------------------------------------------

class PendingItemStatus(str, Enum):
    PENDING = "pending"    # waiting to be included in next order
    ORDERED = "ordered"    # included in a placed order
    SKIPPED = "skipped"    # user chose to skip this week


class PendingItem(Base):
    """
    Free-text items added by the home monitoring agent during the week.
    Accumulates until Monday evening when the agent runs optimization.
    Agent maps item_name → aggregate via LLM; aggregate_id stored once matched.
    """
    __tablename__ = "pending_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    item_name = Column(String, nullable=False)       # free text from agent ("milk", "tahini")
    qty = Column(Float, nullable=False, default=1.0)
    unit = Column(String, nullable=False, default="UNITS")  # "MASS"/"VOLUME"/"UNITS"
    aggregate_id = Column(UUID(as_uuid=True), ForeignKey("aggregates.id"), nullable=True)
    status = Column(SAEnum(PendingItemStatus), nullable=False, default=PendingItemStatus.PENDING)
    added_at = Column(DateTime, default=datetime.utcnow)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    user = relationship("User")
    aggregate = relationship("Aggregate")


class OrderStatus(str, Enum):
    PENDING = "pending"                    # optimization done, cart not built yet
    CART_BUILDING = "cart_building"        # browser automation running
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # cart built, link sent to user
    PLACED = "placed"                      # user provided confirmation number
    FAILED = "failed"                      # automation failed


class Order(Base):
    """
    Represents one shopping run — from optimization result through to placement.
    Created when the agent calls confirm_order() or build_cart().
    Delivery details are denormalised here for simplicity (v1).
    """
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id"), nullable=True)

    # Denormalised for display / history even if store changes
    store_name = Column(String, nullable=False)
    chain_name = Column(String, nullable=False)

    total_cost = Column(Numeric(precision=10, scale=2), nullable=False)
    baseline_cost = Column(Numeric(precision=10, scale=2), nullable=True)  # from HistoricalPurchase

    # Delivery window (as chosen by agent from calendar)
    delivery_window_start = Column(String, nullable=True)   # e.g. "18:00"
    delivery_window_end = Column(String, nullable=True)     # e.g. "21:00"
    delivery_date = Column(String, nullable=True)           # human-readable from Shufersal slot

    # Phase 1 result
    cart_url = Column(Text, nullable=True)                  # sent to user via Telegram
    cart_screenshot_path = Column(Text, nullable=True)      # /tmp/browser_debug/…

    # Phase 2 result (user-provided)
    confirmation_number = Column(String, nullable=True)

    status = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    error_message = Column(Text, nullable=True)             # populated on FAILED

    created_at = Column(DateTime, default=datetime.utcnow)
    placed_at = Column(DateTime, nullable=True)

    user = relationship("User")
    store = relationship("Store")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """
    Line item in an Order. Denormalised so order history is self-contained
    even if the item is delisted or prices change.
    """
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)

    # Catalogue references (nullable — item may be delisted later)
    item_id = Column(UUID(as_uuid=True), ForeignKey("items.id"), nullable=True)
    aggregate_id = Column(UUID(as_uuid=True), ForeignKey("aggregates.id"), nullable=True)

    # Denormalised snapshot at order time
    item_code = Column(String, nullable=False)
    item_name = Column(String, nullable=False)
    aggregate_name = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    unit_of_measure = Column(String, nullable=True)
    package_quantity = Column(Float, nullable=True)

    qty_packages = Column(Integer, nullable=False)           # packages ordered
    unit_price = Column(Numeric(precision=10, scale=2), nullable=False)  # per package
    cost = Column(Numeric(precision=10, scale=2), nullable=False)

    order = relationship("Order", back_populates="items")
    item = relationship("Item")
    aggregate = relationship("Aggregate")
