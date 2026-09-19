import type { ReactNode } from "react";

type IconName = "train" | "plus" | "route" | "clock" | "upload" | "arrow" | "close" | "menu" | "user";
const paths: Record<IconName, ReactNode> = {
  train: <><rect x="5" y="3" width="14" height="15" rx="4" /><path d="M5 10h14M12 3v7M8 18l-2 3m10-3 2 3" /><path d="M8 14h1m6 0h1" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  route: <><circle cx="6" cy="5" r="2" /><circle cx="18" cy="19" r="2" /><path d="M6 7v5a4 4 0 0 0 4 4h4a4 4 0 0 0 4-4V9a4 4 0 0 0-4-4h-2M18 17v-1" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  upload: <><path d="M12 16V4m-4 4 4-4 4 4M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" /></>,
  arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  user: <><circle cx="12" cy="8" r="4" /><path d="M5 21v-2a7 7 0 0 1 14 0v2" /></>,
};
export default function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
