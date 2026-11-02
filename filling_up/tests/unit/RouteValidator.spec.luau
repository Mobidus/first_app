--!nocheck
local Spec = require("../_harness/Spec")
local Loader = require("../_harness/Loader")
local describe, it, expect = Spec.describe, Spec.it, Spec.expect

local Plan = Loader.require("src/shared/Domain/RoomPlan")
local V = Loader.require("src/shared/Domain/RouteValidator")
local Jump = Loader.require("src/shared/Domain/JumpModel")
local Box = Loader.require("src/shared/Util/Box")

local function deepCopy(t)
	if type(t) ~= "table" then
		return t
	end
	local o = {}
	for k, v in t do
		o[k] = deepCopy(v)
	end
	return o
end

local function hasError(report, prefix)
	for _, e in report.errors do
		if string.sub(e, 1, #prefix) == prefix then
			return true
		end
	end
	return false
end

local first = Plan.build(Plan.selectSpec(1, 1234, {}), 1, 1234)

describe("JumpModel (analytic, provisional until T06)", function()
	it("flat reach ~8.67 studs, decreasing with rise, zero above jump height", function()
		expect(Jump.reach(0)).toBeNear(16 * 2 * math.sqrt(2 * 196.2 * 7.2) / 196.2, 1e-9)
		expect(Jump.reach(4) < Jump.reach(0)).toBe(true)
		expect(Jump.reach(7.3)).toBe(0)
	end)
	it("required rise is capped below the physical jump height", function()
		expect(Jump.maxRequiredRise() < Jump.HEIGHT).toBe(true)
		expect(Jump.requiredHopOk(0, 7.0, 0.65)).toBe(false)
	end)
	it("height max and distance max separately allowed can be impossible together", function()
		local rise = Jump.maxRequiredRise()
		local flatMax = 0.65 * Jump.reach(0)
		expect(Jump.requiredHopOk(flatMax, 0, 0.65)).toBe(true)
		expect(Jump.requiredHopOk(flatMax, rise, 0.65)).toBe(false)
	end)
end)

describe("RouteValidator", function()
	it("first room is valid: exit reachable without tool", function()
		local ok, rep = V.validate(first, { gapRatio = first.gapRatio })
		expect(ok).toBe(true)
		expect(rep.checks.hops >= 1).toBe(true)
	end)

	it("exit clearance is exactly 8 x 8 x 10 studs", function()
		expect(first.exitClearance.sx).toBe(8)
		expect(first.exitClearance.sz).toBe(8)
		expect(first.exitClearance.sy).toBe(10)
	end)

	it("detects a solid dropped into the exit clearance", function()
		local r = deepCopy(first)
		local c = r.exitClearance
		table.insert(r.solids, { nodeId = "intruder", kind = "prop", box = Box.new(c.cx, c.cy, c.cz, 2, 2, 2) })
		local ok, rep = V.validate(r, { gapRatio = r.gapRatio })
		expect(ok).toBe(false)
		expect(hasError(rep, "exit_clearance_obstructed")).toBe(true)
	end)

	it("detects a wave mouth above the exit clearance or the last support", function()
		local r = deepCopy(first)
		table.insert(r.waveMouths, Box.new(r.exitClearance.cx, r.size.h - 0.5, r.exitClearance.cz, 10, 1, 10))
		local ok, rep = V.validate(r, { gapRatio = r.gapRatio })
		expect(ok).toBe(false)
		expect(hasError(rep, "mouth_over_exit_clearance")).toBe(true)
	end)

	it("detects a too-long gap instead of accepting it", function()
		local r = deepCopy(first)
		for _, n in r.routeGraph.nodes do
			if n.id == "exit_ledge" then
				n.box.cx += 30
			end
		end
		for _, s in r.solids do
			if s.nodeId == "exit_ledge" then
				s.box.cx += 30
			end
		end
		local ok = V.validate(r, { gapRatio = r.gapRatio })
		expect(ok).toBe(false)
	end)

	it("detects a beam intercepting a jump arc", function()
		local r = deepCopy(first)
		local edge
		for _, e in r.routeGraph.edges do
			if e.from ~= "floor" and e.kind == "jump" then
				edge = e
			end
		end
		if edge == nil then
			return -- single-hop room: covered by generated rooms in generation suites
		end
		local a, b
		for _, n in r.routeGraph.nodes do
			if n.id == edge.from then
				a = n
			elseif n.id == edge.to then
				b = n
			end
		end
		local mx, mz = (a.box.cx + b.box.cx) / 2, (a.box.cz + b.box.cz) / 2
		table.insert(r.solids, { nodeId = "beam", kind = "architecture", box = Box.new(mx, math.max(a.topY, b.topY) + 2.5, mz, 3, 1, 3) })
		local ok, rep = V.validate(r, { gapRatio = r.gapRatio })
		expect(ok).toBe(false)
		expect(hasError(rep, "arc_blocked") or hasError(rep, "head_clearance") or hasError(rep, "solids_overlap")).toBe(true)
	end)

	it("detects an unprotected last support", function()
		local r = deepCopy(first)
		for _, e in r.routeGraph.edges do
			if e.to == r.exitTargetId then
				for _, n in r.routeGraph.nodes do
					if n.id == e.from and n.kind ~= "floor" then
						n.protected = false
					end
				end
			end
		end
		local ok, rep = V.validate(r, { gapRatio = r.gapRatio })
		if first.routeGraph.edges[#first.routeGraph.edges].from ~= "floor" then
			expect(ok).toBe(false)
			expect(hasError(rep, "last_support_not_protected")).toBe(true)
		end
	end)

	it("tutorial cell: floor -> carton (4) -> exit at 8 studs is valid", function()
		local t = Plan.tutorialCell()
		local ok, rep = V.validate(t, { gapRatio = 0.65 })
		if not ok then
			error(table.concat(rep.errors, "; "))
		end
		expect(ok).toBe(true)
		expect(t.routeGraph.nodes[3].topY).toBe(8)
	end)

	it("landing smaller than 7 studs on the required route is rejected", function()
		local r = deepCopy(first)
		for _, n in r.routeGraph.nodes do
			if n.kind == "column" and not n.optional then
				n.walkable = { w = 6, d = 10 }
				break
			end
		end
		local ok, rep = V.validate(r, { gapRatio = r.gapRatio })
		expect(ok).toBe(false)
		expect(hasError(rep, "landing_too_small")).toBe(true)
	end)
end)

return true
