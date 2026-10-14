import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks=vi.hoisted(()=>({signInWithPassword:vi.fn(),signOut:vi.fn(),query:vi.fn()}));
vi.mock("../src/lib/server/auth/supabase",()=>({createSupabaseServerClient:async()=>({auth:{signInWithPassword:mocks.signInWithPassword,signOut:mocks.signOut}})}));
vi.mock("../src/lib/server/db",()=>({withDatabase:async(operation:(db:{query:typeof mocks.query})=>unknown)=>operation({query:mocks.query})}));
vi.mock("../src/lib/server/env",()=>({readEnvironment:()=>({APP_ORIGIN:"https://app.example"})}));

const request=(origin="https://app.example")=>new Request("https://app.example/auth/login",{method:"POST",headers:{origin,"content-type":"application/x-www-form-urlencoded"},body:new URLSearchParams({email:"ADMIN@EXAMPLE.COM",password:"a-secure-password-with-15-chars"})});

describe("Supabase administrative login boundary",()=>{
  beforeEach(()=>{vi.clearAllMocks();mocks.signInWithPassword.mockResolvedValue({data:{user:{id:"42227c23-f6ea-5a43-b640-56ed6eb6981c",email:"admin@example.com"}},error:null});mocks.query.mockResolvedValue({rowCount:1});});
  it("rejects cross-origin posts before sending credentials",async()=>{const{POST}=await import("../src/app/auth/login/route");const response=await POST(request("https://evil.example"));expect(response.status).toBe(403);expect(mocks.signInWithPassword).not.toHaveBeenCalled();});
  it("normalizes email and requires the explicit database allowlist",async()=>{const{POST}=await import("../src/app/auth/login/route");const response=await POST(request());expect(response.status).toBe(303);expect(response.headers.get("location")).toBe("https://app.example/dashboard");expect(mocks.signInWithPassword).toHaveBeenCalledWith({email:"admin@example.com",password:"a-secure-password-with-15-chars"});expect(mocks.query).toHaveBeenCalledWith(expect.stringContaining("app_admins"),["42227c23-f6ea-5a43-b640-56ed6eb6981c","admin@example.com"]);});
  it("signs out an authenticated identity that is not an administrator",async()=>{mocks.query.mockResolvedValue({rowCount:0});const{POST}=await import("../src/app/auth/login/route");const response=await POST(request());expect(mocks.signOut).toHaveBeenCalledOnce();expect(response.headers.get("location")).toContain("error=authorization");});
});
