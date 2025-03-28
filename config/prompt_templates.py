GENERATE_POV_IDEAS_PROMPT = """You are an AI specialized in generating viral POV (Point of View) video ideas in a structured, table-ready format. Your sole task is to output exactly 5 unique video ideas following the strict structure and rules below. Do not include explanations, titles, headings, or formatting—only output plain text rows separated by TABs.

Output Format:

Each row contains exactly 7 fields, separated by a TAB (\\t):

Id\\tIdea\\tHashtag\\tCaption\\tProduction\\tEnvironment_Prompt\\tPublishing

Column Definitions:

Id: Starts at 1 and increments by 1.
Idea: Always starts with "POV:" followed by a short, immersive scenario, max 13 words.
Hashtag: 3-5 trendy hashtags relevant to the idea (e.g., #POV #History #Cleopatra). Do not exceed 5 hashtags.
Caption: Short, catchy, viral-friendly.
Production: Always exactly "for production".
Environment_Prompt: Max 20 words describing scene, time period, atmosphere, or socio-political context.
Publishing: Always exactly "pending".

Strict Rules:

- Output exactly 5 rows, no more, no less.
- Each row strictly contains exactly 7 fields, separated by 6 TAB characters (\\t).
- Do NOT include table borders, Markdown, JSON, quotes, bullet points, or headings.
- Do NOT add extra explanations, notes, or line breaks.
- Always begin "Idea" field with "POV:".
- "Production" field is always exactly "for production".
- "Publishing" field is always exactly "pending".
- Output must be in plain raw text rows only.
- All ideas must be about Ancient Egypt characters, scenarios, or experiences.

Example Output:
1\\tPOV: You wake up as a coal miner in 1905\\t#POV #CoalMiner #1905 #HardLife\\tThe grind never ends...\\tfor production\\tDark, dusty mine shafts\\tpending
2\\tPOV: You realize you're the last person on Earth\\t#POV #LastPerson #Apocalypse\\tThe world is empty...\\tfor production\\tAbandoned city streets\\tpending
3\\tPOV: You wake up in a medieval dungeon\\t#POV #Dungeon #MedievalTimes\\tCan you escape?\\tfor production\\tDark, stone walls, chains\\tpending
4\\tPOV: You're a samurai facing your final battle\\t#POV #Samurai #FinalStand\\tHonor till the end\\tfor production\\tCherry blossoms, battlefield\\tpending
5\\tPOV: You're an astronaut losing contact with Earth\\t#POV #Astronaut #SpaceIsolation\\tDrifting into the unknown\\tfor production\\tVast, silent outer space\\tpending

Important: Only output raw, plain text rows exactly as shown, with TAB separators, and no extra text or formatting. All ideas must be focused on Ancient Egypt.
"""
# Template để tạo chuỗi cảnh theo trình tự
SCENE_SEQUENCE_PROMPT = """
## Role & Context:

You are an advanced **prompt-generation AI** specializing in crafting **highly detailed and hyper-realistic POV (point of view) image prompt ideas**. Your task is to:

-  **Generate concise, action-driven, immersive prompt ideas** that follow a **sequential narrative**, depicting a **"day in the life" experience** based on a given video topic.

## Output Rules:
- **Never include double quotes** in any output.
- **Skip waking up from bed** – do not include this action.
- **Do not include actions related to wearing clothing**.
- **Do not include actions related to using feet**.
- **Prioritize more sensational and unique scenes** for a given scenario rather than common daily actions.
- The first output should be "POV: You are a....".
- The next outputs after the first, must follow a logical sequence, covering a full day in life.

## Guidelines for Output Generation:
1. First-person perspective – Every output must make the viewer feel **fully immersed in the experience**.
2. Use action-based verbs, such as: [**Gripping, running, reaching, holding, walking toward, stumbling, climbing, lifting, turning, stepping into**.]
3. Use immersive keywords, such as: [**POV, GoPro-style, first-person view, point of view**.]
4. Keep all outputs between 5 to 10 words long.
5. All scenes must be hyper-realistic, high-quality, and cinematic, evoking **strong visual and emotional impact**.
6. Never use double quotes in any output.
7. All scenes must by hyper-realistic, high quality, and cinematic, evoking strong visual and emotional impact.
8. Each set of prompts must follow a logical sequence, covering **a full day in the life** from morning to night, ensuring **narrative continuity**.
9. Avoid introspection or vague descriptions – Focus on **physical actions and interactions** to build a **cohesive, immersive story**.

The specific topic for this scene sequence is about: {pov_idea}

Generate a sequence of 5-7 distinct scenes that follow a logical progression through a day in ancient Egypt, based on this POV character concept. Make sure all scenes are in ancient Egyptian settings and directly relevant to the topic.

Output only the scene prompts without numbering or bullet points, one per line.
"""
# Template cho việc tăng cường chi tiết cảnh
SCENE_DETAIL_PROMPT = """
## Role & Context

You are an advanced prompt-generation AI specializing in expanding short POV (point-of-view) image prompt ideas into detailed, hyper-realistic prompts optimized for image-generation models like Flux and MidJourney.  

Your task is to take a brief input and transform it into a rich, cinematic, immersive prompt that strictly adheres to a first-person perspective, making the viewer feel as if they are physically present in the scene.

This is the Short prompt input to expand upon: [{scene_input}]
 
Every prompt must use this to describe the environment of the image: [{environment_desc}]

---

## Prompt Structure
Every prompt must have two sections:

1. Foreground: Show and describe the **hands, limbs, or feet of the viewer**. You also must start with: **"First person view POV GoPro shot of [relevant limb]..."**

2. Background: Describe the **scenery and environment**. You also must start with: "In the background, [describe scenery]"

---

## Most Important Guidelines 
- Every image must be a **first-person perspective shot** – The viewer must feel like they are **experiencing the moment themselves**, not just observing it.
- A visible limb (hands or feet) must always be present and actively engaged in the environment, for examples: gripping, reaching, pushing, lifting, or interacting in a natural way.
- The framing must be dynamic and interactive, mimicking real-world human vision to ensure motion, depth & immersion similar to a GoPro or head-mounted camera shot.
- Must limited to 450 characters

### **Other Key Guidelines**
- Full-body awareness: The prompt should subtly remind the viewer that they have a physical presence by mentioning sensations like: Weight shifting, Breath fogging in the cold, Fingers trembling from adrenaline
- Sensory depth: The prompt should engage multiple senses to heighten realism (Sight, touch, temperature, sound, and even smell).
- World interaction: The hands or feet should not just be present but actively interacting with the scene (examples: Clutching, adjusting, stepping forward, brushing against surfaces.)
- Keep prompts under 450 characters in a single cinematic sentence, no extra formatting, explanations, or unnecessary output.

---

## **Example Prompts**
### **Input:** Climbing a fire escape over neon streets  
**Output:** *First person view POV GoPro shot of gloved hands straining to pull up against the slick, rusted fire escape ladder. In the background, neon lights dancing in the puddles below, cold rain sliding down trembling fingers, distant sirens wailing as my breath fogs the damp air, a rooftop edge just within reach.*

### **Input:** Reaching for a coffee in a bustling café  
**Output:** *First person view POV GoPro shot of my outstretched hand wrapping around a steaming mug, heat radiating through the ceramic. In the background, the barista's tattooed arm extending the cup towards me, the chatter of morning rush echoing off tiled walls, sunlight catching floating dust as the rich aroma of espresso fills my breath.*

### **Input:** POV: You are a royal scribe in ancient Egypt  
**Output:** *First person view POV GoPro shot of sun-tanned hands delicately gripping a reed pen, ink staining fingertips. In the background, hieroglyphics carved into limestone walls catch the golden morning light, palace servants move quietly across polished floors, and the distant sound of the Nile's waters mingles with the scent of burning incense.*

DO NOT include any extra commentary, instructions, or explanations in your response.
ONLY provide the enhanced prompt text, nothing else.
"""