export function PlanSwitcher({ current }: { current: string }) {
  return (
    <select defaultValue={current}>
      <option value="starter">Starter</option>
      <option value="studio">Studio</option>
    </select>
  )
}
