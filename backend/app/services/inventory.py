from decimal import Decimal
from typing import Callable

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.api import (
    CampaignBackupInventory,
    CampaignBackupInventoryItem,
    CampaignBackupInventoryMember,
    CampaignBackupPurse,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
    InventoryMemberRead,
    InventoryRead,
    InventoryUpdate,
    MoneyAmount,
    PurseBalances,
    PurseRead,
    PurseUpdate,
)
from app.models.database import (
    CharacterProfile,
    CurrencyBalance,
    Inventory,
    InventoryAccess,
    InventoryItem,
    Person,
    Purse,
)
from app.models.enums import (
    CurrencyDenomination,
    InventoryAccessRole,
)
from app.services.campaign_context import CampaignContext


COPPER_PER_GOLD = Decimal("100")


class InventoryService:
    def __init__(self, context: CampaignContext):
        self.context = context
        self.db = context.db

    @staticmethod
    def money_to_copper(value: MoneyAmount) -> int:
        copper = (
            value.amount
            * value.denomination.value_in_gp
            * COPPER_PER_GOLD
        )
        integral_copper = copper.to_integral_value()
        if copper != integral_copper:
            raise ValueError(
                "Value must resolve to a whole number of copper pieces"
            )
        return int(integral_copper)

    @staticmethod
    def copper_to_money(value_cp: int) -> MoneyAmount:
        return MoneyAmount(
            amount=Decimal(value_cp) / COPPER_PER_GOLD,
            denomination=CurrencyDenomination.GOLD,
        )

    def _add_empty_purse(self, inventory_id: int) -> None:
        self.db.add(Purse(inventory_id=inventory_id))
        self.db.add_all(
            [
                CurrencyBalance(
                    purse_id=inventory_id,
                    denomination=denomination,
                    amount=0,
                )
                for denomination in CurrencyDenomination
            ]
        )

    def _active_character_belongs_to_campaign(self) -> bool:
        person_id = self.context.campaign.active_character_person_id
        if (
            person_id is None
            or self.db.get(CharacterProfile, person_id) is None
        ):
            return False
        person = self.db.get(Person, person_id)
        return (
            person is not None
            and person.campaign_id == self.context.campaign_id
        )

    def stage_ensure_default(self) -> Inventory:
        """Repair the default inventory in the caller-owned transaction."""
        inventory = self.db.exec(
            select(Inventory)
            .where(Inventory.campaign_id == self.context.campaign_id)
            .order_by(Inventory.id)
        ).first()
        if inventory is None:
            inventory = Inventory(campaign_id=self.context.campaign_id)
            self.db.add(inventory)
            self.db.flush()

        if self.db.get(Purse, inventory.id) is None:
            self._add_empty_purse(inventory.id)
            self.db.flush()
        else:
            existing_denominations = set(
                self.db.exec(
                    select(CurrencyBalance.denomination).where(
                        CurrencyBalance.purse_id == inventory.id
                    )
                ).all()
            )
            missing_balances = [
                CurrencyBalance(
                    purse_id=inventory.id,
                    denomination=denomination,
                    amount=0,
                )
                for denomination in CurrencyDenomination
                if denomination not in existing_denominations
            ]
            if missing_balances:
                self.db.add_all(missing_balances)
                self.db.flush()

        if (
            self._active_character_belongs_to_campaign()
            and self.db.get(
                InventoryAccess,
                (
                    inventory.id,
                    self.context.campaign.active_character_person_id,
                ),
            )
            is None
        ):
            self.db.add(
                InventoryAccess(
                    inventory_id=inventory.id,
                    character_person_id=(
                        self.context.campaign.active_character_person_id
                    ),
                    role=InventoryAccessRole.OWNER,
                )
            )
            self.db.flush()

        return inventory

    def stage_sync_default_owner(self) -> Inventory:
        """Replace default-inventory grants in the caller-owned transaction."""
        inventory = self.stage_ensure_default()
        grants = self.db.exec(
            select(InventoryAccess).where(
                InventoryAccess.inventory_id == inventory.id
            )
        ).all()
        for grant in grants:
            self.db.delete(grant)
        self.db.flush()

        if self._active_character_belongs_to_campaign():
            self.db.add(
                InventoryAccess(
                    inventory_id=inventory.id,
                    character_person_id=(
                        self.context.campaign.active_character_person_id
                    ),
                    role=InventoryAccessRole.OWNER,
                )
            )
            self.db.flush()
        return inventory

    def to_read(
        self,
        inventory: Inventory,
    ) -> InventoryRead:
        balances_by_denomination = {
            balance.denomination: balance.amount
            for balance in self.db.exec(
                select(CurrencyBalance).where(
                    CurrencyBalance.purse_id == inventory.id
                )
            ).all()
        }
        purse_balances = PurseBalances(
            **{
                denomination.value: balances_by_denomination.get(
                    denomination,
                    0,
                )
                for denomination in CurrencyDenomination
            }
        )
        purse_total_gp = sum(
            (
                Decimal(amount) * denomination.value_in_gp
                for denomination, amount in balances_by_denomination.items()
            ),
            start=Decimal("0"),
        )

        member_rows = self.db.exec(
            select(InventoryAccess, Person)
            .join(
                CharacterProfile,
                (
                    CharacterProfile.person_id
                    == InventoryAccess.character_person_id
                ),
            )
            .join(Person, Person.id == CharacterProfile.person_id)
            .where(InventoryAccess.inventory_id == inventory.id)
            .order_by(Person.name, Person.id)
        ).all()
        members = [
            InventoryMemberRead(
                character_person_id=person.id,
                character_name=person.name,
                role=grant.role,
                is_active_character=(
                    self.context.campaign.active_character_person_id
                    == person.id
                ),
            )
            for grant, person in member_rows
        ]

        stored_items = self.db.exec(
            select(InventoryItem)
            .where(InventoryItem.inventory_id == inventory.id)
            .order_by(InventoryItem.id)
        ).all()
        items = [
            InventoryItemRead(
                id=item.id,
                name=item.name,
                description=item.description,
                category=item.category,
                rarity=item.rarity,
                quantity=item.quantity,
                unit_value=(
                    self.copper_to_money(item.unit_value_cp)
                    if item.unit_value_cp is not None
                    else None
                ),
                total_value=(
                    self.copper_to_money(
                        item.unit_value_cp * item.quantity
                    )
                    if item.unit_value_cp is not None
                    else None
                ),
            )
            for item in stored_items
        ]

        return InventoryRead(
            id=inventory.id,
            campaign_id=self.context.campaign_id,
            name=inventory.name,
            description=inventory.description,
            members=members,
            purse=PurseRead(
                balances=purse_balances,
                total_value=MoneyAmount(
                    amount=purse_total_gp,
                    denomination=CurrencyDenomination.GOLD,
                ),
            ),
            items=items,
        )

    def _commit_staged(
        self,
        operation: Callable[[], Inventory],
    ) -> InventoryRead:
        try:
            inventory = operation()
            self.db.commit()
            self.db.refresh(inventory)
            return self.to_read(inventory)
        except Exception:
            self.db.rollback()
            raise

    def get_default(self) -> InventoryRead:
        return self._commit_staged(
            lambda: self.stage_ensure_default(),
        )

    def stage_update_metadata(
        self,
        update: InventoryUpdate,
    ) -> Inventory:
        inventory = self.stage_ensure_default()

        if "name" in update.model_fields_set:
            name = update.name.strip()
            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Inventory name cannot be blank",
                )
            inventory.name = name
        if "description" in update.model_fields_set:
            inventory.description = update.description.strip()

        self.db.add(inventory)
        self.db.flush()
        return inventory

    def update_metadata(
        self,
        update: InventoryUpdate,
    ) -> InventoryRead:
        return self._commit_staged(
            lambda: self.stage_update_metadata(update),
        )

    def stage_update_purse(
        self,
        update: PurseUpdate,
    ) -> Inventory:
        inventory = self.stage_ensure_default()
        for field_name in update.balances.model_fields_set:
            denomination = CurrencyDenomination(field_name)
            balance = self.db.get(
                CurrencyBalance,
                (inventory.id, denomination),
            )
            balance.amount = getattr(update.balances, field_name)
            self.db.add(balance)
        self.db.flush()
        return inventory

    def update_purse(
        self,
        update: PurseUpdate,
    ) -> InventoryRead:
        return self._commit_staged(
            lambda: self.stage_update_purse(update),
        )

    def get_item(
        self,
        inventory: Inventory,
        item_id: int,
    ) -> InventoryItem:
        item = self.db.get(InventoryItem, item_id)
        if item is None or item.inventory_id != inventory.id:
            raise HTTPException(
                status_code=404,
                detail="Inventory item not found",
            )
        return item

    def _convert_item_value(self, value: MoneyAmount | None) -> int | None:
        try:
            return (
                self.money_to_copper(value)
                if value is not None
                else None
            )
        except ValueError as error:
            raise HTTPException(
                status_code=422,
                detail=str(error),
            ) from error

    def stage_create_item(
        self,
        item_data: InventoryItemCreate,
    ) -> Inventory:
        inventory = self.stage_ensure_default()
        name = item_data.name.strip()
        if not name:
            raise HTTPException(
                status_code=422,
                detail="Item name cannot be blank",
            )

        self.db.add(
            InventoryItem(
                inventory_id=inventory.id,
                name=name,
                description=item_data.description.strip(),
                category=item_data.category,
                rarity=item_data.rarity,
                quantity=item_data.quantity,
                unit_value_cp=self._convert_item_value(
                    item_data.unit_value
                ),
            )
        )
        self.db.flush()
        return inventory

    def create_item(
        self,
        item_data: InventoryItemCreate,
    ) -> InventoryRead:
        return self._commit_staged(
            lambda: self.stage_create_item(item_data),
        )

    def stage_update_item(
        self,
        item_id: int,
        update: InventoryItemUpdate,
    ) -> Inventory:
        inventory = self.stage_ensure_default()
        item = self.get_item(inventory, item_id)

        if "name" in update.model_fields_set:
            name = update.name.strip()
            if not name:
                raise HTTPException(
                    status_code=422,
                    detail="Item name cannot be blank",
                )
            item.name = name
        if "description" in update.model_fields_set:
            item.description = update.description.strip()
        if "category" in update.model_fields_set:
            item.category = update.category
        if "rarity" in update.model_fields_set:
            item.rarity = update.rarity
        if "quantity" in update.model_fields_set:
            item.quantity = update.quantity
        if "unit_value" in update.model_fields_set:
            item.unit_value_cp = self._convert_item_value(
                update.unit_value
            )

        self.db.add(item)
        self.db.flush()
        return inventory

    def update_item(
        self,
        item_id: int,
        update: InventoryItemUpdate,
    ) -> InventoryRead:
        return self._commit_staged(
            lambda: self.stage_update_item(
                item_id,
                update,
            ),
        )

    def stage_delete_item(
        self,
        item_id: int,
    ) -> Inventory:
        inventory = self.stage_ensure_default()
        self.db.delete(self.get_item(inventory, item_id))
        self.db.flush()
        return inventory

    def delete_item(
        self,
        item_id: int,
    ) -> InventoryRead:
        return self._commit_staged(
            lambda: self.stage_delete_item(item_id),
        )

    def to_backup(self, inventory: Inventory) -> CampaignBackupInventory:
        balances = {
            balance.denomination: balance.amount
            for balance in self.db.exec(
                select(CurrencyBalance).where(
                    CurrencyBalance.purse_id == inventory.id
                )
            ).all()
        }
        members = self.db.exec(
            select(InventoryAccess)
            .where(InventoryAccess.inventory_id == inventory.id)
            .order_by(InventoryAccess.character_person_id)
        ).all()
        items = self.db.exec(
            select(InventoryItem)
            .where(InventoryItem.inventory_id == inventory.id)
            .order_by(InventoryItem.id)
        ).all()

        return CampaignBackupInventory(
            name=inventory.name,
            description=inventory.description,
            purse=CampaignBackupPurse(
                **{
                    denomination.value: balances.get(denomination, 0)
                    for denomination in CurrencyDenomination
                }
            ),
            members=[
                CampaignBackupInventoryMember(
                    person_backup_id=member.character_person_id,
                    role=member.role,
                )
                for member in members
            ],
            items=[
                CampaignBackupInventoryItem(
                    name=item.name,
                    description=item.description,
                    category=item.category,
                    rarity=item.rarity,
                    quantity=item.quantity,
                    unit_value_cp=item.unit_value_cp,
                )
                for item in items
            ],
        )

    def list_backup_entries(self) -> list[CampaignBackupInventory]:
        inventories = self.db.exec(
            select(Inventory)
            .where(
                Inventory.campaign_id == self.context.campaign_id
            )
            .order_by(Inventory.id)
        ).all()
        return [self.to_backup(inventory) for inventory in inventories]

    def stage_restore_backups(
        self,
        inventory_backups: list[CampaignBackupInventory],
        person_id_map: dict[int, int],
    ) -> None:
        """Restore inventories within the backup service transaction."""
        default_inventory = self.stage_ensure_default()

        for index, inventory_backup in enumerate(inventory_backups):
            if index == 0:
                inventory = default_inventory
            else:
                inventory = Inventory(
                    campaign_id=self.context.campaign_id
                )
                self.db.add(inventory)
                self.db.flush()
                self.db.add(Purse(inventory_id=inventory.id))
                self.db.flush()

            inventory.name = inventory_backup.name
            inventory.description = inventory_backup.description
            self.db.add(inventory)
            self.db.flush()

            existing_balances = {
                balance.denomination: balance
                for balance in self.db.exec(
                    select(CurrencyBalance).where(
                        CurrencyBalance.purse_id == inventory.id
                    )
                ).all()
            }
            for denomination in CurrencyDenomination:
                balance = existing_balances.get(denomination)
                amount = getattr(
                    inventory_backup.purse,
                    denomination.value,
                )
                if balance is None:
                    balance = CurrencyBalance(
                        purse_id=inventory.id,
                        denomination=denomination,
                    )
                balance.amount = amount
                self.db.add(balance)

            existing_items = self.db.exec(
                select(InventoryItem).where(
                    InventoryItem.inventory_id == inventory.id
                )
            ).all()
            for item in existing_items:
                self.db.delete(item)

            existing_grants = self.db.exec(
                select(InventoryAccess).where(
                    InventoryAccess.inventory_id == inventory.id
                )
            ).all()
            for grant in existing_grants:
                self.db.delete(grant)
            self.db.flush()

            for item_backup in inventory_backup.items:
                self.db.add(
                    InventoryItem(
                        inventory_id=inventory.id,
                        name=item_backup.name,
                        description=item_backup.description,
                        category=item_backup.category,
                        rarity=item_backup.rarity,
                        quantity=item_backup.quantity,
                        unit_value_cp=item_backup.unit_value_cp,
                    )
                )

            for member_backup in inventory_backup.members:
                character_person_id = person_id_map.get(
                    member_backup.person_backup_id
                )
                if (
                    character_person_id is None
                    or self.db.get(
                        CharacterProfile,
                        character_person_id,
                    )
                    is None
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Inventory access references a missing "
                            "character profile"
                        ),
                    )
                self.db.add(
                    InventoryAccess(
                        inventory_id=inventory.id,
                        character_person_id=character_person_id,
                        role=member_backup.role,
                    )
                )
            self.db.flush()
