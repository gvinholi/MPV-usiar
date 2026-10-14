export const USIAR_V1_ID = "33eba713-de4c-5dd0-a8b3-ac6375975ede";
export const USIAR_V2_ID = "42227c23-f6ea-5a43-b640-56ed6eb6981c";
export type Category = "context" | "ambiguous_context" | "excluded_context" | "maintenance" | "sanitization" | "installation" | "purchase" | "parts";
export type Profile = { id: string; code: "USIAR"; version: "v1" | "v2"; name: string; associationWindow?: number; terms: Record<Category, readonly string[]> };

const contextV1 = ["ar condicionado","ar-condicionado","climatização","sistema de climatização","hvac","aparelhos de climatização","equipamentos de climatização","condicionador de ar","condicionadores de ar","split","chiller","chillers","vrf","vrv","fan coil","fancoil","central de ar","sistema de refrigeração","aparelhos de ar condicionado","equipamentos de ar condicionado"];
const maintenanceV1 = ["manutenção preventiva","manutenção corretiva","manutenção preventiva e corretiva","manutenção","serviços de manutenção","serviços continuados de manutenção"];
const sanitizationV1 = ["higienização","higienização de aparelhos","limpeza técnica","limpeza de aparelhos"];
const installationV1 = ["instalação","instalações","instalação de aparelhos"];
const purchaseV1 = ["aquisição","compra","fornecimento","fornecimento de equipamentos","aquisição de aparelhos"];
const partsV1 = ["peças","componentes","peças de reposição","fornecimento de peças","aquisição de peças","fornecimento de componentes"];

export const usiarV1: Profile = { id: USIAR_V1_ID, code: "USIAR", version: "v1", name: "Usinaria — manutenção e higienização de climatização", terms: { context: contextV1, ambiguous_context: [], excluded_context: [], maintenance: maintenanceV1, sanitization: sanitizationV1, installation: installationV1, purchase: purchaseV1, parts: partsV1 } };
export const usiarV2: Profile = { id: USIAR_V2_ID, code: "USIAR", version: "v2", name: "UsiAr — triagem contextual de climatização", associationWindow: 1, terms: {
  context: ["ar condicionado","ar-condicionado","climatização","sistema de climatização","sistemas de climatização","equipamento de climatização","equipamentos de climatização","condicionador de ar","condicionadores de ar","aparelho de ar condicionado","aparelhos de ar condicionado","equipamento de ar condicionado","equipamentos de ar condicionado","aparelho split","aparelhos split","sistema split","sistemas split","multi split","multi-split","multisplit","vrf","vrv","evaporadora","evaporadoras","condensadora","condensadoras","chiller","chillers","sistema central de climatização","sistemas centrais de climatização","ar condicionado central","ar-condicionado central","central de ar","sistema hvac","sistemas hvac","duto de ar condicionado","dutos de ar condicionado","duto de climatização","dutos de climatização","pmoc","plano de manutenção operação e controle"],
  ambiguous_context: ["hvac","refrigeração","sistema de refrigeração","sistemas de refrigeração","equipamento de refrigeração","equipamentos de refrigeração"],
  excluded_context: ["ar condicionado veicular","ar-condicionado veicular","climatização veicular"],
  maintenance: ["manutenção","manutenção preventiva","manutenção corretiva","manutenção preventiva e corretiva","manutenção corretiva e preventiva","serviço de manutenção","serviços de manutenção","pmoc","plano de manutenção operação e controle"],
  sanitization: ["higienização","limpeza","desinfecção","limpeza e higienização","limpeza e desinfecção","limpeza de duto","limpeza de dutos"],
  installation: ["instalação","instalações","instalação de aparelho","instalação de aparelhos","desinstalação","reinstalação"],
  purchase: ["aquisição","compra","fornecimento","fornecimento de equipamento","fornecimento de equipamentos","aquisição de aparelho","aquisição de aparelhos"],
  parts: ["peça","peças","componente","componentes","peça de reposição","peças de reposição","fornecimento de peças","fornecimento de componentes"],
} };
