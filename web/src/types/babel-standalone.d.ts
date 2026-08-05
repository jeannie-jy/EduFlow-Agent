/**
 * @babel/standalone 类型声明（包本身不带类型）。
 * 仅声明 SandboxRenderer 用到的 transform 子集。
 */

declare module "@babel/standalone" {
  export interface BabelTransformResult {
    code: string | null;
    map?: unknown;
    ast?: unknown;
  }

  export interface BabelTransformOptions {
    presets?: unknown[];
    plugins?: unknown[];
    filename?: string;
    sourceType?: "script" | "module" | "unambiguous";
  }

  const Babel: {
    transform(code: string, options?: BabelTransformOptions): BabelTransformResult;
  };

  export default Babel;
}
