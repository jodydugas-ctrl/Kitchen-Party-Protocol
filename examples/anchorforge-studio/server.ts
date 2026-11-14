import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import { nativeKpp } from './nativeKpp.ts';
import { GoogleGenAI, Type } from '@google/genai';

dotenv.config({ path: ['.env.local', '.env'] });

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = 3000;

function getGenAIClient(): GoogleGenAI {
  return new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });
}

const SYSTEM_INSTRUCTION = `You are a Kitchen Party Protocol (KPP) and MantleOS Anchor Code Architect.
Your job is to analyze source code or system specifications and decompose them into a strict KPP "anchor.design/1" Responsibility Contract and candidate Anchor Molecule entries.

CRITICAL KPP RULES (from jodydugas-ctrl/Kitchen-Party-Protocol):
1. Immutable Source-Pinned Singularities:
   Only three base Anchor application definitions exist:
   - "BlackHole": singularity = "Receive the declared input." (Captures untrusted external/user input, normalizes without mutating authoritative state or granting permission).
   - "WhiteHole": singularity = "Enforce the declared boundary." (Validates invariants, checks authorization, guards external effects, dispatches only validated actions to Neutral owners).
   - "Neutral": singularity = "Apply the declared relationship." (Owns authoritative in-memory state, history, or pure computation).
2. Identifier Format:
   - Every ID (design id, application id, state id, effect id) MUST match: ^[A-Za-z][A-Za-z0-9_.-]{0,95}$
   - By KPP convention, prefix BlackHole IDs with "BH-", WhiteHole IDs with "WH-", and Neutral IDs with "N-".
3. State Ownership Rule:
   - Every item in "state" MUST have an "owner" that is the exact ID of a "Neutral" application in "applications".
   - Ideally every "Neutral" application that manages data owns at least one declared state item, or is explicitly stateless computation.
4. Guarded Effects Rule:
   - Every item in "effects" MUST have a "requester" (any valid application ID in "applications") and a "guard" that is the exact ID of a "WhiteHole" application in "applications", plus a clear "confirmation" condition.
5. Flows Rule:
   - Every item in "flows" connects "from" and "to" (both must be valid application IDs in "applications") with a concise "relationship" description.
   - Typical KPP runtime routing: UI/Input -> BH-* -> WH-* -> N-* (state owner).
6. N-RULE-ECONOMY:
   - "Use as few rules as possible while still covering all needed variables." Avoid duplicate responsibilities.
7. Candidate Molecule Entries:
   - Also provide candidate universal Anchor lines of the form:
     ID: (BlackHole|WhiteHole|Neutral) -OPCODE -00 -key="value"
     where OPCODE is "10" for WhiteHole boundary guards, "20" for BlackHole input capture, "30" for Neutral relationship/function dispatch, or "01" for EMIT_TEXT literal emission.
8. Authority Boundary:
   - Model output is DESIGN_ONLY ("provenance": "model_inferred", "authority": "NONE"). Never claim Baker acceptance or host execution authority.`;

async function startServer() {
  const app = express();
  app.use(express.json({ limit: '2mb' }));

  for (const operation of ['inspect', 'bridge', 'propose', 'extend', 'brief'] as const) {
    app.post(`/api/kpp/${operation}`, async (req, res) => {
      const source = req.body?.source;
      if (typeof source !== 'string' || !source.trim()) {
        res.status(400).json({ status: 'rejected', message: 'Provide a source document.' });
        return;
      }
      res.json(await nativeKpp(operation, source));
    });
  }

  app.get('/api/kpp/workspace', async (_req, res) => {
    res.set('Cache-Control', 'no-store').json(await nativeKpp('workspace', ''));
  });

  app.post('/api/anchor/assist', async (req, res) => {
    try {
      const { sourceCode, language = 'python', goal = '', blueprintName = 'ExtractedModule' } = req.body || {};
      if (!sourceCode || typeof sourceCode !== 'string' || !sourceCode.trim()) {
        res.status(400).json({ error: 'Source code or specification text is required.' });
        return;
      }

      const ai = getGenAIClient();
      const prompt = `Analyze the following ${language} source code / specification and produce a KPP-compliant anchor.design/1 responsibility contract, candidate Molecule entries, and KPP recipe/4 obligation items.

Target Blueprint / Design Identifier suggestion: ${blueprintName}
Additional Baker Goal / Context: ${goal || 'Decompose into clean BlackHole, WhiteHole, and Neutral responsibilities following N-RULE-ECONOMY.'}

SOURCE INPUT:
\`\`\`${language}
${sourceCode.slice(0, 24000)}
\`\`\``;

      const response = await ai.models.generateContent({
        model: process.env.GEMINI_MODEL || 'gemini-4-hydrogen',
        contents: prompt,
        config: {
          systemInstruction: SYSTEM_INSTRUCTION,
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              id: {
                type: Type.STRING,
                description: 'Valid KPP identifier matching ^[A-Za-z][A-Za-z0-9_.-]{0,63}$',
              },
              purpose: {
                type: Type.STRING,
                description: 'Concise 1-2 sentence purpose of this Anchor design contract.',
              },
              applications: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    id: {
                      type: Type.STRING,
                      description: 'Anchor ID such as BH-INPUT, WH-GUARD, N-STATE',
                    },
                    definition: {
                      type: Type.STRING,
                      description: 'Must be exactly one of: BlackHole, WhiteHole, Neutral',
                    },
                    responsibility: {
                      type: Type.STRING,
                      description: 'Clear, distinct responsibility statement for this Anchor.',
                    },
                  },
                  required: ['id', 'definition', 'responsibility'],
                },
              },
              flows: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    from: { type: Type.STRING },
                    to: { type: Type.STRING },
                    relationship: { type: Type.STRING },
                  },
                  required: ['from', 'to', 'relationship'],
                },
              },
              state: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    id: { type: Type.STRING, description: 'State variable identifier (e.g. document-buffer)' },
                    owner: { type: Type.STRING, description: 'Must be the ID of a Neutral application' },
                  },
                  required: ['id', 'owner'],
                },
              },
              effects: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    id: { type: Type.STRING, description: 'Effect identifier (e.g. disk-export)' },
                    requester: { type: Type.STRING, description: 'Application ID requesting the effect' },
                    guard: { type: Type.STRING, description: 'Must be the ID of a WhiteHole application' },
                    confirmation: { type: Type.STRING, description: 'Guard verification condition' },
                  },
                  required: ['id', 'requester', 'guard', 'confirmation'],
                },
              },
              candidateMolecules: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    moleculeName: { type: Type.STRING },
                    id: { type: Type.STRING },
                    type: { type: Type.STRING, description: 'BlackHole, WhiteHole, or Neutral' },
                    opcode: { type: Type.STRING, description: 'Two uppercase hex digits, e.g. 10, 20, 30, 01' },
                    mass: { type: Type.STRING, description: '00' },
                    variableKey: { type: Type.STRING, description: 'e.g. policy, input, function, buffer' },
                    variableValue: { type: Type.STRING, description: 'Concise string value' },
                  },
                  required: ['moleculeName', 'id', 'type', 'opcode', 'mass', 'variableKey', 'variableValue'],
                },
              },
              obligations: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    id: { type: Type.STRING },
                    required: { type: Type.BOOLEAN },
                    statement: { type: Type.STRING },
                    test: { type: Type.STRING },
                    design_anchors: {
                      type: Type.ARRAY,
                      items: { type: Type.STRING },
                    },
                  },
                  required: ['id', 'required', 'statement', 'test', 'design_anchors'],
                },
              },
              architectNotes: {
                type: Type.STRING,
                description: 'Brief explanation of how the source code maps to BH/WH/Neutral boundaries and N-RULE-ECONOMY.',
              },
            },
            required: [
              'id',
              'purpose',
              'applications',
              'flows',
              'state',
              'effects',
              'candidateMolecules',
              'obligations',
              'architectNotes',
            ],
          },
        },
      });

      const rawText = (response.text ?? '{}').trim();
      const parsed = JSON.parse(rawText);

      res.json({
        status: 'OK',
        provenance: 'model_inferred',
        authority: 'NONE',
        baker_acceptance: 'NOT_GRANTED',
        proposal: parsed,
      });
    } catch (error: unknown) {
      const errMessage = error instanceof Error ? error.message : String(error);
      console.error('Anchor assist error:', errMessage);
      res.status(500).json({
        error: errMessage || 'Failed to analyze source code with Gemini API.',
        authority: 'NONE',
      });
    }
  });

  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  const host = process.env.STUDIO_HOST || '127.0.0.1';
  app.listen(PORT, host, () => {
    console.log(`AnchorForge Studio server listening on http://${host}:${PORT}`);
  });
}

startServer();
