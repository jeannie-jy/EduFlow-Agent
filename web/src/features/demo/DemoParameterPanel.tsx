type DemoParameterPanelProps = {
  edgeWeight: number;
  speed: number;
  onEdgeWeightChange(value: number): void;
  onSpeedChange(value: number): void;
};

export function DemoParameterPanel({
  edgeWeight,
  speed,
  onEdgeWeightChange,
  onSpeedChange,
}: DemoParameterPanelProps) {
  return (
    <aside aria-labelledby="demo-parameters-title" className="demo-parameter-panel paper-surface">
      <p className="demo-eyebrow">参数调整</p>
      <h3 id="demo-parameters-title">调整一条边，观察路径重算</h3>
      <div className="demo-parameter-panel__field">
        <div>
          <label htmlFor="demo-b-d-weight">B 到 D 的边权重</label>
          <output htmlFor="demo-b-d-weight">{edgeWeight}</output>
        </div>
        <input
          id="demo-b-d-weight"
          type="range"
          min="3"
          max="9"
          step="1"
          value={edgeWeight}
          onChange={(event) => onEdgeWeightChange(Number(event.target.value))}
        />
        <p>这是唯一可编辑的图边；修改后会在本地即时重算。</p>
      </div>
      <div className="demo-parameter-panel__field">
        <div>
          <label htmlFor="demo-playback-speed">自动演示速度</label>
          <output htmlFor="demo-playback-speed">{speed}×</output>
        </div>
        <input
          id="demo-playback-speed"
          type="range"
          min="0.75"
          max="1.5"
          step="0.25"
          value={speed}
          onChange={(event) => onSpeedChange(Number(event.target.value))}
        />
      </div>
    </aside>
  );
}
