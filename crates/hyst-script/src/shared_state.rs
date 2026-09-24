//! The shared named-state namespace (plan §4 R3): scripts write into it, any output reads from
//! it. Plain data only — no functions, no references to other scripts — so it can't become a
//! disguised script-to-script call. One instance lives in a `ScriptEngine`, `Rc`-shared into
//! every script's Lua VM as a `shared.get(name)`/`shared.set(name, value)` global table.

use std::cell::RefCell;
use std::collections::HashMap;
use std::rc::Rc;

#[derive(Debug, Clone, PartialEq)]
pub enum SharedValue {
    Number(f64),
    Bool(bool),
    Str(String),
}

#[derive(Debug, Clone, Default)]
pub struct SharedState {
    map: HashMap<String, SharedValue>,
}

impl SharedState {
    pub fn get(&self, name: &str) -> Option<&SharedValue> {
        self.map.get(name)
    }

    pub fn set(&mut self, name: String, value: SharedValue) {
        self.map.insert(name, value);
    }
}

pub type SharedStateHandle = Rc<RefCell<SharedState>>;

pub fn new_handle() -> SharedStateHandle {
    Rc::new(RefCell::new(SharedState::default()))
}

/// Binds a `shared` global table onto `lua`, backed by `handle`. Every script VM gets its own
/// `shared` global bound to the SAME handle, so writes from one script's frame are visible to a
/// later-run script (deterministic order, plan-required) and to outputs after the frame — without
/// any script ever holding a callable reference into another script.
pub fn bind_shared_global(lua: &mlua::Lua, handle: SharedStateHandle) -> mlua::Result<()> {
    let table = lua.create_table()?;

    let get_handle = handle.clone();
    let get = lua.create_function(move |lua, name: String| {
        let state = get_handle.borrow();
        match state.get(&name) {
            Some(SharedValue::Number(n)) => (*n).into_lua(lua),
            Some(SharedValue::Bool(b)) => (*b).into_lua(lua),
            Some(SharedValue::Str(s)) => s.clone().into_lua(lua),
            None => Ok(mlua::Value::Nil),
        }
    })?;
    table.set("get", get)?;

    let set_handle = handle;
    let set = lua.create_function(move |_, (name, value): (String, mlua::Value)| {
        let converted = match value {
            mlua::Value::Number(n) => Some(SharedValue::Number(n)),
            mlua::Value::Integer(n) => Some(SharedValue::Number(n as f64)),
            mlua::Value::Boolean(b) => Some(SharedValue::Bool(b)),
            mlua::Value::String(s) => Some(SharedValue::Str(s.to_str()?.to_string())),
            _ => None,
        };
        if let Some(v) = converted {
            set_handle.borrow_mut().set(name, v);
        }
        Ok(())
    })?;
    table.set("set", set)?;

    lua.globals().set("shared", table)
}

use mlua::IntoLua;

#[cfg(test)]
mod tests {
    use super::*;
    use mlua::Lua;

    #[test]
    fn script_writes_are_visible_to_a_second_vm_sharing_the_handle() {
        let handle = new_handle();

        let lua_a = Lua::new();
        bind_shared_global(&lua_a, handle.clone()).unwrap();
        lua_a.load(r#"shared.set("mood", 0.75)"#).exec().unwrap();

        let lua_b = Lua::new();
        bind_shared_global(&lua_b, handle).unwrap();
        let got: f64 = lua_b.load(r#"return shared.get("mood")"#).eval().unwrap();
        assert_eq!(got, 0.75);
    }

    #[test]
    fn missing_key_reads_as_nil() {
        let handle = new_handle();
        let lua = Lua::new();
        bind_shared_global(&lua, handle).unwrap();
        let got: mlua::Value = lua.load(r#"return shared.get("nope")"#).eval().unwrap();
        assert!(got.is_nil());
    }
}
