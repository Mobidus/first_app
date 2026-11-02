--!strict
-- Public contracts (docs/05_ARCHITECTURE_ET_TESTS.md §4–5). Type-only module.

export type ExpeditionPhase = "Preparing" | "Active" | "Transitioning" | "Suspended" | "KO" | "Extracted"

export type KOCause = "confirmed_burial" | "marked_kill_volume"

export type Checkpoint = {
	runId: string,
	seed: number,
	configVersion: string,
	depth: number,
	roomRewardMask: number,
	lastCommittedDepth: number,
	checkpointRevision: number,
	roomInstanceId: string,
	chargesSnapshot: { [string]: number }?,
	rateBasisPoints: number,
	paidBaseCumulative: number,
}

export type RoomMastery = {
	totalCompleted: number,
	families: { [string]: number },
	firstRebirthQualified: boolean,
}

export type EquippedLoadout = {
	active: string?,
	passive: string?,
	companion: string?,
	trail: string?,
	tool_skin: string?,
	landing_fx: string?,
	victory_fx: string?,
	workshop_skin: string?,
}

export type PurchaseLedger = {
	-- receiptId (PurchaseId) -> true once durably granted (contract extension, decision 0005)
	receipts: { [string]: boolean },
	receiptOrder: { string },
	entitlements: { [string]: boolean },
}

export type PlayerProfile = {
	schemaVersion: number,
	revision: number,
	coins: number,
	xp: number,
	permits: number,
	rebirthCount: number,
	ownedTools: { [string]: boolean },
	toolRanks: { [string]: number },
	ownedCosmetics: { [string]: boolean },
	equippedLoadout: EquippedLoadout,
	roomMastery: RoomMastery,
	bestDepth: number,
	tutorialFlags: { [string]: boolean },
	checkpoint: Checkpoint?,
	settings: { reducedEffects: boolean, language: string, ghostHints: boolean },
	purchaseLedger: PurchaseLedger,
}

export type ExpeditionState = {
	runId: string,
	seed: number,
	configVersion: string,
	controllerProfileId: string,
	depth: number,
	state: ExpeditionPhase,
	roomId: string,
	waveIndex: number,
	roomRewardMask: number,
	lastCommittedDepth: number,
	equippedLoadoutSnapshot: EquippedLoadout,
	checkpointRevision: number,
	koCause: KOCause?,
	transitionsCommitted: number,
	resumed: boolean,
}

export type Box = { cx: number, cy: number, cz: number, sx: number, sy: number, sz: number }

export type RouteNode = {
	id: string,
	kind: "floor" | "column" | "exit_ledge",
	box: Box, -- collider top surface box of the node (studs, room-local, y = up)
	topY: number,
	walkable: { w: number, d: number },
	stack: { { propId: string, box: Box } },
	arrival: "present" | "wave1",
	behavior: string,
	protected: boolean,
}

export type RouteEdge = { from: string, to: string, gap: number, rise: number, kind: "jump" | "walk" }

export type RoomDefinition = {
	templateId: string,
	familyId: string,
	formatId: string,
	exitType: string,
	seed: number,
	depth: number,
	size: { w: number, d: number, h: number },
	routeGraph: { nodes: { RouteNode }, edges: { RouteEdge } },
	spawnZones: { Box },
	safeZones: { Box },
	exitClearance: Box,
	exitOpening: Box,
	waveMouths: { Box },
	collisionBudget: { dynamic: number, static: number, decor: number },
	themeManifestId: string,
	tokens: { { id: number, x: number, y: number, z: number } },
	milestoneHeights: { number },
	fallback: boolean,
	diagnostics: { string },
}

export type ImpactEvent = {
	objectInstanceId: string,
	serverTime: number,
	impactNormal: { x: number, y: number, z: number },
	impactStrength: number,
	settleState: "falling" | "impact" | "settling" | "supporting",
}

return {}
