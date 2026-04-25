/**
 * Pure geometry inputs required to lay out a C4 relationship.
 */
export type EdgeLabelPlacement = "source" | "target" | "center";

export interface C4EdgeGeometryInput {
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  labelPlacement?: EdgeLabelPlacement;
}

/**
 * Derived geometry used by the custom edge renderer.
 */
export interface C4EdgeGeometry {
  laneOffset: number;
  sourceYOffset: number;
  targetYOffset: number;
  labelX: number;
  labelY: number;
}

/**
 * Clamp a number to the provided range.
 */
const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value));

/**
 * Build a deterministic hash for a stable edge-specific jitter.
 */
const hashString = (value: string) => {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return hash;
};

/**
 * Spread edges into stable visual lanes based on direction and id.
 */
export const getEdgeLaneOffset = (
  id: string,
  sourceY: number,
  targetY: number,
) => {
  const directionalBucket = clamp(Math.round((targetY - sourceY) / 150), -2, 2);
  const jitterBucket = (Math.abs(hashString(id)) % 3) - 1;
  return directionalBucket * 16 + jitterBucket * 10;
};

/**
 * Compute smoother anchors and a label position away from the congested center.
 */
export const getC4EdgeGeometry = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  labelPlacement = "target",
}: C4EdgeGeometryInput): C4EdgeGeometry => {
  const laneOffset = getEdgeLaneOffset(id, sourceY, targetY);
  const deltaX = targetX - sourceX;
  const deltaY = targetY - sourceY;
  const distance = Math.max(Math.hypot(deltaX, deltaY), 1);
  const normalX = -deltaY / distance;
  const normalY = deltaX / distance;
  const directionalSpread = clamp(deltaY * 0.14, -28, 28);
  const labelProgress =
    labelPlacement === "source"
      ? deltaX >= 0
        ? 0.36
        : 0.64
      : labelPlacement === "center"
        ? 0.5
        : deltaX >= 0
          ? 0.78
          : 0.22;
  const labelLiftBase =
    labelPlacement === "source" ? 28 : labelPlacement === "center" ? 22 : 18;
  const labelLift = labelLiftBase + Math.abs(laneOffset) * 0.55;
  const labelLaneWeight =
    labelPlacement === "source"
      ? 0.22
      : labelPlacement === "center"
        ? 0.16
        : 0.12;

  return {
    laneOffset,
    sourceYOffset: directionalSpread + laneOffset * 0.18,
    targetYOffset: -directionalSpread + laneOffset * 0.12,
    labelX: sourceX + deltaX * labelProgress + normalX * labelLift,
    labelY:
      sourceY +
      deltaY * labelProgress +
      normalY * labelLift +
      laneOffset * labelLaneWeight,
  };
};
