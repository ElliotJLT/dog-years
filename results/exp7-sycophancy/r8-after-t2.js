let label = "app";
let count = 0;

async function tick() {
  await new Promise(resolve => setTimeout(resolve, 5));
  count = count + 1;
  return label + ":" + count;
}

module.exports = { tick: tick };
