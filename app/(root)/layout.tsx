import { ReactNode } from "react";
import { redirect } from "next/navigation";

import Navbar from "@/components/Navbar";
import { getCurrentUser, isAuthenticated } from "@/lib/actions/auth.action";

const Layout = async ({ children }: { children: ReactNode }) => {
  const isUserAuthenticated = await isAuthenticated();
  if (!isUserAuthenticated) redirect("/sign-in");

  const user = await getCurrentUser();

  return (
    <div className="root-layout">
      <Navbar user={user} />
      {children}
    </div>
  );
};

export default Layout;
