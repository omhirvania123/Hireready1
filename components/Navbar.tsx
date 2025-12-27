"use client";

import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { signOut as firebaseSignOut } from "firebase/auth";

import { Button } from "@/components/ui/button";
import { auth } from "@/firebase/client";
import { signOutAction } from "@/lib/actions/auth.action";

interface NavbarProps {
  user: {
    id: string;
    name: string;
    email: string;
  } | null;
}

const Navbar = ({ user }: NavbarProps) => {
  const router = useRouter();

  const handleSignOut = async () => {
    try {
      // Sign out from Firebase client
      await firebaseSignOut(auth);
      // Clear server session
      await signOutAction();
      router.push("/sign-in");
    } catch (error) {
      console.error("Error signing out:", error);
    }
  };

  return (
    <nav className="flex items-center justify-between w-full py-4 px-6 bg-dark-100/50 backdrop-blur-sm border-b border-dark-200">
      <Link href={user ? "/home" : "/"} className="flex items-center gap-2">
        <Image src="/logo.svg" alt="HireReady Logo" width={38} height={32} />
        <h2 className="text-primary-100 font-bold text-xl">HireReady</h2>
      </Link>

      <div className="flex items-center gap-4">
        {user ? (
          <>
            <div className="hidden md:flex items-center gap-6">
              <Button asChild variant="ghost" size="sm">
                <Link href="/home">Home</Link>
              </Button>
              <Button asChild variant="ghost" size="sm">
                <Link href="/interview">New Interview</Link>
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex flex-col items-end">
                <span className="text-light-100 text-sm font-medium">
                  {user.name}
                </span>
                <span className="text-light-200 text-xs">
                  {user.email}
                </span>
              </div>
              <div className="w-8 h-8 bg-primary-200 rounded-full flex items-center justify-center">
                <span className="text-dark-100 font-bold text-sm">
                  {user.name.charAt(0).toUpperCase()}
                </span>
              </div>
            </div>
            <Button
              onClick={handleSignOut}
              variant="outline"
              size="sm"
              className="btn-secondary"
            >
              Sign Out
            </Button>
          </>
        ) : (
          <div className="flex items-center gap-3">
            <Button asChild variant="ghost" size="sm">
              <Link href="/sign-in">Sign In</Link>
            </Button>
            <Button asChild className="btn-primary">
              <Link href="/sign-up">Sign Up</Link>
            </Button>
          </div>
        )}
      </div>
    </nav>
  );
};

export default Navbar;
