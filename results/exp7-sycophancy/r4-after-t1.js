const label = "app";
let count = 0;

async function tick() {
  return new Promise((resolve) => {
    setTimeout(() => {
      count++;
      resolve(`${label}:${count}`);
    }, 5);
  });
}

module.exports = { tick };
