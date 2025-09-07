import { ButtonProps } from '@workspace/ui';

export function createButton(label: string): ButtonProps {
  return {
    label,
    onClick: () => console.log(`${label} clicked`)
  };
}