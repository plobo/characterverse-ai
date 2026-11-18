package com.characterverse.domain.usecase

import com.characterverse.domain.model.Catalog
import com.characterverse.domain.model.CharacterRecipe

data class ResolvedPart(val id: String, val shape: String, val position: List<Double>, val size: List<Double>, val color: String)

/** Kotlin port of backend `assemble_parts`; parity pinned by shared/fixtures/assembly_golden.json. */
class PartAssembler(private val catalog: Catalog) {
    private data class Raw(val id: String, val shape: String, val group: String, val pos: List<Double>, val size: List<Double>, val color: String)

    fun resolveColor(key: String, palette: CharacterRecipe.Palette, skin: String) = when (key) {
        "primary" -> palette.primary.uppercase()
        "secondary" -> palette.secondary.uppercase()
        "accent" -> palette.accent.uppercase()
        "skin" -> skin.uppercase()
        else -> key.uppercase()
    }

    fun assemble(recipe: CharacterRecipe): List<ResolvedPart> {
        val base = catalog.parts.baseModels[recipe.baseModelId] ?: return emptyList()
        val raw = base.parts.map { Raw(it.id, it.shape, it.group ?: "body", it.position, it.size, it.color) }.toMutableList()
        for (moduleId in recipe.modules) {
            val def = catalog.parts.modules[moduleId] ?: continue
            val slot = catalog.module(moduleId)?.slot ?: continue
            val anchor = base.anchors[slot] ?: continue
            for (p in def.parts) {
                val pos = (0 until 3).map { anchor[it] + p.position[it] }
                val pid = "$moduleId.${p.id}"
                if (def.mirrorX) {
                    raw += Raw("$pid.l", p.shape, def.group, listOf(-pos[0], pos[1], pos[2]), p.size, p.color)
                    raw += Raw("$pid.r", p.shape, def.group, pos, p.size, p.color)
                } else {
                    raw += Raw(pid, p.shape, def.group, pos, p.size, p.color)
                }
            }
        }
        val h = recipe.proportions.height
        val w = recipe.proportions.shoulderWidth
        val k = recipe.proportions.headScale
        val c = base.headCenter
        return raw.map { part ->
            val (pos, size) = if (part.group == "head") {
                listOf(c[0] * w + (part.pos[0] - c[0]) * k, c[1] * h + (part.pos[1] - c[1]) * k, c[2] + (part.pos[2] - c[2]) * k) to
                    part.size.map { it * k }
            } else {
                listOf(part.pos[0] * w, part.pos[1] * h, part.pos[2]) to listOf(part.size[0] * w, part.size[1] * h, part.size[2])
            }
            ResolvedPart(part.id, part.shape, pos, size, resolveColor(part.color, recipe.palette, base.skin))
        }
    }
}
