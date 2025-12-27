import Link from "next/link";
import Image from "next/image";
import { redirect } from "next/navigation";

import { Button } from "@/components/ui/button";
import { isAuthenticated } from "@/lib/actions/auth.action";

const RootPage = async () => {
  const isUserAuthenticated = await isAuthenticated();
  
  if (isUserAuthenticated) {
    redirect("/home");
  }

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-4xl mx-auto text-center">
          <div className="mb-8">
            <Image
              src="/robot.png"
              alt="AI Interview Assistant"
              width={200}
              height={200}
              className="mx-auto mb-6"
            />
            <h1 className="text-4xl md:text-6xl font-bold text-primary-100 mb-4">
              Master Your Interviews with AI
            </h1>
            <p className="text-xl text-light-100 mb-8 max-w-2xl mx-auto">
              Practice real interview questions with our AI-powered platform. 
              Get instant feedback and improve your skills with personalized coaching.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Button asChild size="lg" className="btn-primary text-lg px-8 py-4">
              <Link href="/sign-up">Get Started Free</Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="btn-secondary text-lg px-8 py-4">
              <Link href="/sign-in">Sign In</Link>
            </Button>
          </div>

          <div className="mt-12 grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-200 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🎯</span>
              </div>
              <h3 className="text-lg font-semibold text-light-100 mb-2">AI-Powered Practice</h3>
              <p className="text-light-200">Realistic interview scenarios with intelligent AI assistants</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-200 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">📊</span>
              </div>
              <h3 className="text-lg font-semibold text-light-100 mb-2">Instant Feedback</h3>
              <p className="text-light-200">Get detailed analysis and improvement suggestions</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-primary-200 rounded-full flex items-center justify-center mx-auto mb-4">
                <span className="text-2xl">🚀</span>
              </div>
              <h3 className="text-lg font-semibold text-light-100 mb-2">Track Progress</h3>
              <p className="text-light-200">Monitor your improvement over time</p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default RootPage;
