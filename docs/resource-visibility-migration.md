# Resource visibility migration matrix

Milestone 3 keeps existing campaign content campaign-wide while establishing
the ownership and authorization seams needed for later private resources.
Access to every row below is currently derived from an authenticated
`CampaignContext`; possession of a campaign or resource ID is not sufficient.

| Resource | Current visibility | Future creator field | Future visibility/grant work |
| --- | --- | --- | --- |
| Campaign | Membership-scoped | `created_by_user_id` | Campaign defaults will define new-resource visibility. |
| Episode and rolls | Campaign-wide | Episode creator | Add visibility to the episode aggregate; rolls inherit it. |
| Person and character profile | Campaign-wide; character writes are assignment-scoped | Person/profile creator | Character-private fields may be separated from the shared person record. |
| Character notes and backstory | Explicit `campaign`, `restricted`, or `private`; campaign role remains the capability ceiling | `created_by_user_id` implemented | Access owner and normalized resource-specific grants are enforced across CRUD, search, tags, references, and portable exports. |
| Location | Campaign-wide | Location creator | Add visibility and grants if private world information is introduced. |
| Faction | Campaign-wide | Faction creator | Add visibility and grants if private world information is introduced. |
| Inventory, purse, and items | Campaign-wide | Inventory/item creator | Reconcile campaign role policy with inventory-specific grants. |
| Tags and relationships | Inherit owning resource | No independent creator initially | Queries must inherit the owning resource's visibility and never reveal hidden labels. |
| Uploaded images | Inherit owning resource | No independent creator | Asset authorization must resolve the owner record before serving bytes. |
| Campaign backup | Owner-only full campaign export | Export actor is audited | Later filtered exports include only records visible to the requesting user. |

For each remaining resource-specific privacy expansion, the schema change must
include
`created_by_user_id`, a campaign-default visibility value, any explicit grant
table required by that resource, query filtering, indirect tag/search filtering,
asset filtering, and backup filtering in one migration. Nullable compatibility
columns must not be treated as public access.
