-- ============================================
-- 丘天财作品集 — Supabase 数据库初始化脚本
-- 在 Supabase SQL Editor 中运行
-- ============================================

-- 1. 作品表
CREATE TABLE IF NOT EXISTS works (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  category TEXT DEFAULT '',
  description TEXT DEFAULT '',
  tags TEXT[] DEFAULT '{}',
  image TEXT DEFAULT '',
  video TEXT DEFAULT '',
  color TEXT DEFAULT '#8ab4f8',
  "order" INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 工具表（单行，upsert 模式）
CREATE TABLE IF NOT EXISTS tools (
  id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  data JSONB NOT NULL DEFAULT '[]'::jsonb,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 允许公开读取（RLS 已默认开启，需要显式授权）
ALTER TABLE works ENABLE ROW LEVEL SECURITY;
ALTER TABLE tools ENABLE ROW LEVEL SECURITY;

CREATE POLICY "允许公开读取作品" ON works FOR SELECT USING (true);
CREATE POLICY "允许公开读取工具" ON tools FOR SELECT USING (true);

-- 4. 插入默认作品（表为空时）
INSERT INTO works (id, title, category, description, tags, image, video, color, "order")
SELECT * FROM (VALUES
  ('blender', '三维科幻短片', '01 / 3D 动画', '独立完成科幻飞船与空间场景建模、材质、灯光设计，设计镜头运动与动画节奏——全流程 Blender 作品。', ARRAY['Blender', '建模', '灯光渲染'], '', '', '#ff9955', 1),
  ('ue5',     'UE5 场景设计',  '02 / 实时引擎', '使用 Lumen / Nanite 搭建雪地、沙漠、海洋实时场景，完成场景构图、灯光设计与镜头展示。', ARRAY['UE5', 'Lumen', 'Nanite'], '', '', '#ffffff', 2),
  ('aigc',    'AI 场景生成',  '03 / AIGC', 'SD + ControlNet 线稿→成品，Depth/Lineart 控制结构稳定，ComfyUI 搭建完整工作流——科幻/卡牌/二次元。', ARRAY['Stable Diffusion', 'ComfyUI', 'ControlNet'], '', '', '#a855f7', 3),
  ('ae',      '游戏抽卡动画', '04 / 动态设计', 'AE 完成卡牌抽卡动画全流程：出卡、特效、节奏设计，独立整合角色/卡框/背景素材，符合商业化需求。', ARRAY['After Effects', 'Motion Design', '节奏设计'], '', '', '#9999ff', 4),
  ('ua',      'UA 视频制作',  '05 / 游戏买量', '日产 6 条信息流前贴，面向 30-40 岁男性受众，6 大钩子类型体系，口播+红包+实机——完整 UA 管线。', ARRAY['UA 买量', '口播文案', '数据分析'], '', '', '#ff3333', 5),
  ('social',  '信息流剪辑',  '06 / 短视频', '抖音/小红书账号视觉内容制作，PR/AE 剪辑包装，数据驱动优化——单条最高 15W+ 播放。', ARRAY['Premiere Pro', 'AE', '抖音运营'], '', '', '#00cccc', 6)
) AS v(id, title, category, description, tags, image, video, color, "order")
WHERE NOT EXISTS (SELECT 1 FROM works LIMIT 1);
