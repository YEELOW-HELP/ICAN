import { configureStore, createSlice, type PayloadAction } from "@reduxjs/toolkit";
import { sessionStorageKeys } from "../api/client";

type AuthState = {
  adminToken: string | null;
  adminEmail: string | null;
};

const authSlice = createSlice({
  name: "auth",
  initialState: {
    adminToken: localStorage.getItem(sessionStorageKeys.admin),
    adminEmail: localStorage.getItem("mnp_admin_email"),
  } as AuthState,
  reducers: {
    signedIn(state, action: PayloadAction<{ token: string; email: string }>) {
      state.adminToken = action.payload.token;
      state.adminEmail = action.payload.email;
      localStorage.setItem("mnp_admin_email", action.payload.email);
    },
    signedOut(state) {
      state.adminToken = null;
      state.adminEmail = null;
      localStorage.removeItem(sessionStorageKeys.admin);
      localStorage.removeItem("mnp_admin_email");
    },
  },
});

export const { signedIn, signedOut } = authSlice.actions;
export const store = configureStore({ reducer: { auth: authSlice.reducer } });
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
