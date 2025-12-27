import { ReactNode } from "react";
import { redirect } from "next/navigation";

import Navbar from "@/components/Navbar";
import { isAuthenticated } from "@/lib/actions/auth.action";

const PublicLayout = async ({ children }: { children: ReactNode }) => {
  const isUserAuthenticated = await isAuthenticated();
  if (isUserAuthenticated) redirect("/");

  return (
    <div className="root-layout">
      <Navbar user={null} />
      {children}
    </div>
  );
};

export default PublicLayout;
