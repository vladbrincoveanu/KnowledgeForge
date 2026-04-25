declare module "react-cytoscapejs" {
  import { ComponentType } from "react";

  interface CytoscapeComponentProps {
    elements: any[];
    style?: React.CSSProperties;
    stylesheet?: any[];
    layout?: any;
    cy?: (cy: any) => void;
    [key: string]: any;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
