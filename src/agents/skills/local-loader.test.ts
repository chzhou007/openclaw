import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { loadSkillsFromDirSafe } from "./local-loader.js";

const tempDirs: string[] = [];

async function createTempSkillsRoot(): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "openclaw-skills-local-loader-"));
  tempDirs.push(dir);
  return dir;
}

afterEach(async () => {
  await Promise.all(tempDirs.splice(0).map((dir) => fs.rm(dir, { recursive: true, force: true })));
});

describe("loadSkillsFromDirSafe description fallback", () => {
  it("parses a heading fallback in <name> - <description> format", async () => {
    const skillsRoot = await createTempSkillsRoot();
    const skillDir = path.join(skillsRoot, "stock-technical-analysis");
    await fs.mkdir(skillDir, { recursive: true });
    await fs.writeFile(
      path.join(skillDir, "SKILL.md"),
      "# stock-technical-analysis - 数据驱动的技术分析（按需生成）\n\nbody\n",
      "utf8",
    );

    const loaded = loadSkillsFromDirSafe({ dir: skillsRoot, source: "project" });
    expect(loaded.skills).toHaveLength(1);
    expect(loaded.skills[0]?.name).toBe("stock-technical-analysis");
    expect(loaded.skills[0]?.description).toBe("数据驱动的技术分析（按需生成）");
  });

  it("parses a non-heading fallback line in <name> - <description> format", async () => {
    const skillsRoot = await createTempSkillsRoot();
    const skillDir = path.join(skillsRoot, "multi-factor-strategy");
    await fs.mkdir(skillDir, { recursive: true });
    await fs.writeFile(
      path.join(skillDir, "SKILL.md"),
      "multi-factor-strategy - 创建多因子选股策略\n",
      "utf8",
    );

    const loaded = loadSkillsFromDirSafe({ dir: skillsRoot, source: "project" });
    expect(loaded.skills).toHaveLength(1);
    expect(loaded.skills[0]?.name).toBe("multi-factor-strategy");
    expect(loaded.skills[0]?.description).toBe("创建多因子选股策略");
  });

  it("uses the first non-empty body line when no name-prefixed fallback exists", async () => {
    const skillsRoot = await createTempSkillsRoot();
    const skillDir = path.join(skillsRoot, "multi-factor-strategy");
    await fs.mkdir(skillDir, { recursive: true });
    await fs.writeFile(
      path.join(skillDir, "SKILL.md"),
      "# multi-factor-strategy\n\n基于 Tushare 的多因子选股与回测流程。\n",
      "utf8",
    );

    const loaded = loadSkillsFromDirSafe({ dir: skillsRoot, source: "project" });
    expect(loaded.skills).toHaveLength(1);
    expect(loaded.skills[0]?.description).toBe("基于 Tushare 的多因子选股与回测流程。");
  });
});
