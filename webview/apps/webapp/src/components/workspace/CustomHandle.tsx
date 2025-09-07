import { Handle, HandleProps } from "@xyflow/react";

export const CustomHandle = (props: HandleProps) => {
  return (
    <Handle
      style={{
        border: "none",
        backgroundColor: "transparent",
      }}
      {...props}
    />
  );
};
