type ResourceWithId = {
  id: number
}

type NamedResource = ResourceWithId & {
  name: string
}

type NumberedSession = ResourceWithId & {
  sessionNumber: number
}

type UpdatedResource = ResourceWithId & {
  updatedAt: string
}

type ResourceComparator<T> = (left: T, right: T) => number

export function upsertById<T extends ResourceWithId>(
  resources: T[],
  resource: T,
  compare: ResourceComparator<T>,
): T[] {
  const exists = resources.some(
    (candidate) => candidate.id === resource.id,
  )
  const updated = exists
    ? resources.map((candidate) =>
        candidate.id === resource.id ? resource : candidate
      )
    : [...resources, resource]

  return updated.sort(compare)
}

export function removeById<T extends ResourceWithId>(
  resources: T[],
  deletedId: number,
): T[] {
  return resources.filter((resource) => resource.id !== deletedId)
}

export function compareById(
  left: ResourceWithId,
  right: ResourceWithId,
): number {
  return left.id - right.id
}

export function compareByName(
  left: NamedResource,
  right: NamedResource,
): number {
  return (
    left.name.localeCompare(
      right.name,
      undefined,
      { sensitivity: "base" },
    )
    || left.id - right.id
  )
}

export function compareBySessionNumberDescending(
  left: NumberedSession,
  right: NumberedSession,
): number {
  return right.sessionNumber - left.sessionNumber || right.id - left.id
}

export function compareByUpdatedAtDescending(
  left: UpdatedResource,
  right: UpdatedResource,
): number {
  return (
    right.updatedAt.localeCompare(left.updatedAt)
    || right.id - left.id
  )
}
