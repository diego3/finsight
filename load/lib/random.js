// Local helpers so scenarios don't need to fetch remote jslib modules at runtime.

export function uuidv4() {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

const FIRST = ["Ada", "Grace", "Alan", "Katherine", "Edsger", "Barbara", "Donald", "Linus"];
const LAST = ["Lovelace", "Hopper", "Turing", "Johnson", "Dijkstra", "Liskov", "Knuth", "Torvalds"];

export function randomName() {
  const pick = (xs) => xs[Math.floor(Math.random() * xs.length)];
  return `${pick(FIRST)} ${pick(LAST)}`;
}
