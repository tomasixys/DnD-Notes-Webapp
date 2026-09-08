import type { CampaignChangeDto } from "../types/DataTransferObjects"

export type ResourceEditor = {
  campaignId: number
  resourceType: string
  resourceId: number | null
  revision?: number
}

export function changeAffectsEditor(
  change: CampaignChangeDto,
  editor: ResourceEditor,
  campaignId: number,
): boolean {
  return editor.campaignId === campaignId
    && editor.resourceId !== null
    && editor.resourceType === change.resourceType
    && editor.resourceId === change.resourceId
    && (change.action === "deleted" || change.revision === null
      || editor.revision === undefined || change.revision > editor.revision)
}
