import InterviewForm from "@/components/InterviewForm";
import { getCurrentUser } from "@/lib/actions/auth.action";
import { redirect } from "next/navigation";

const Page = async () => {
  const user = await getCurrentUser();

  if (!user?.id) {
    redirect("/sign-in");
  }

  return (
    <>
      <InterviewForm userId={user.id} />
    </>
  );
};

export default Page;